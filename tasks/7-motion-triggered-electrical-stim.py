"""Movement-triggered electrical stimulation recording task.

This lean task records camera and MotSen1 motion, waits for stationary trial
starts, sends one movement-qualified trigger to the cl_stim movement-triggered
server, logs returned stimulation markers, and starts the next intertrial only
after stim_off.
"""

from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'intertrial',
    'trial',
    'stopped',
]

events = [
    'session_timer',
    'state_timer',
    'stim_delay_timer',
    'stim_timeout_timer',
    'motion',
    'cursor_update',
    'stop_button',
]

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session and trial timing.
v.session_duration = 45 * minute
v.intertrial_duration = 2 * second
v.motion_wait_time = 0.5 * second

# Motion sensor parameters.
v.motion_threshold = 3
v.cpi = 100

# Stimulation trigger modes:
#   'motion_event_count' -> trigger after v.stim_required_motion_events.
#   'first_motion_delay' -> trigger v.stim_motion_delay after first motion.
v.stim_trigger_mode = 'motion_event_count'
v.stim_required_motion_events = 3
v.stim_motion_delay = 100 * ms
v.stim_timeout = 10 * second
v.stim_trigger_code = 1
v.code_session_marker_to_stim = 0

# Marker codes received from cl_stim/config.toml [pycontrol_events.codes].
v.code_stim_on = 101
v.code_stim_off = 102
v.code_stim_pulse = 103
v.code_stim_sham = 104
v.code_session_start = 110
v.code_session_end = 111

# Trial and stimulation tracking.
v.trial_number = 0
v.motion_count = 0
v.motion_events_this_trial = 0
v.last_motion_time = 0
v.first_motion_seen = False
v.stim_sent_this_trial = False
v.awaiting_stim_offset = False
v.stim_active = False
v.stim_trigger_count = 0
v.marker_count = 0
v.stim_on_count = 0
v.stim_off_count = 0
v.stim_sham_count = 0
v.stim_pulse_count = 0
v.unknown_marker_count = 0
v.stim_timeout_count = 0
v.intertrial_start_time = 0

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def send_to_stim(code):
    """Send a 2-byte code to the cl_stim trigger server over bci_link UART."""
    if hasattr(hw, 'bci_link'):
        hw.bci_link.send_int_to_bci(code)
        return True
    print('{}, missing_bci_link'.format(get_current_time()))
    return False


def marker_name(code):
    if code == v.code_stim_on:
        return 'stim_on'
    if code == v.code_stim_off:
        return 'stim_off'
    if code == v.code_stim_pulse:
        return 'stim_pulse'
    if code == v.code_stim_sham:
        return 'stim_sham'
    if code == v.code_session_start:
        return 'session_start'
    if code == v.code_session_end:
        return 'session_end'
    return 'unknown'


def set_stim_sync(active):
    if not hasattr(hw, 'stim_sync'):
        return
    if active:
        hw.stim_sync.on()
        print('{}, stim_sync_ttl_on'.format(get_current_time()))
    else:
        hw.stim_sync.off()
        print('{}, stim_sync_ttl_off'.format(get_current_time()))


def log_marker(code):
    """Record a stimulation marker echoed back by the cl_stim server."""
    name = marker_name(code)
    v.marker_count += 1

    if name == 'stim_on':
        v.stim_on_count += 1
        v.stim_active = True
        set_stim_sync(True)
    elif name == 'stim_off':
        v.stim_off_count += 1
        v.stim_active = False
        set_stim_sync(False)
    elif name == 'stim_sham':
        v.stim_sham_count += 1
        v.stim_active = False
        set_stim_sync(False)
    elif name == 'stim_pulse':
        v.stim_pulse_count += 1
        v.stim_active = False
        set_stim_sync(False)
    elif name == 'unknown':
        v.unknown_marker_count += 1

    print(
        '{}, external_stim_marker code={} name={} count={} active={}'.format(
            get_current_time(), code, name, v.marker_count, v.stim_active
        )
    )
    return name


def print_summary():
    print(
        '{}, movement_triggered_stim_summary trials={} triggers={} markers={} '
        'stim_on={} stim_off={} stim_sham={} stim_pulse={} unknown={} '
        'timeouts={} motion={}'.format(
            get_current_time(),
            v.trial_number,
            v.stim_trigger_count,
            v.marker_count,
            v.stim_on_count,
            v.stim_off_count,
            v.stim_sham_count,
            v.stim_pulse_count,
            v.unknown_marker_count,
            v.stim_timeout_count,
            v.motion_count,
        )
    )


def stim_delay_ms():
    return int(v.stim_motion_delay / ms)


def validate_stim_trigger_mode():
    if v.stim_trigger_mode not in ('motion_event_count', 'first_motion_delay'):
        print(
            '{}, invalid_stim_trigger_mode mode={} using=motion_event_count'.format(
                get_current_time(), v.stim_trigger_mode
            )
        )
        v.stim_trigger_mode = 'motion_event_count'

    if int(v.stim_required_motion_events) < 1:
        print('{}, invalid_stim_required_motion_events using=1'.format(get_current_time()))
        v.stim_required_motion_events = 1


def reset_trial_tracking():
    v.motion_events_this_trial = 0
    v.first_motion_seen = False
    v.stim_sent_this_trial = False
    v.awaiting_stim_offset = False
    v.stim_active = False
    disarm_timer('stim_delay_timer')
    disarm_timer('stim_timeout_timer')
    set_stim_sync(False)


def trigger_stim(reason):
    """Send one movement-qualified stimulation trigger for the current trial."""
    if v.stim_sent_this_trial:
        return

    v.stim_sent_this_trial = True
    v.awaiting_stim_offset = True
    disarm_timer('stim_delay_timer')

    if send_to_stim(v.stim_trigger_code):
        v.stim_trigger_count += 1
        set_timer('stim_timeout_timer', v.stim_timeout)
        print(
            '{}, stim_trigger_sent trial={} code={} reason={} mode={} '
            'motion_events={} delay_ms={} trigger_count={}'.format(
                get_current_time(),
                v.trial_number,
                v.stim_trigger_code,
                reason,
                v.stim_trigger_mode,
                v.motion_events_this_trial,
                stim_delay_ms(),
                v.stim_trigger_count,
            )
        )
    else:
        v.awaiting_stim_offset = False
        print(
            '{}, stim_trigger_send_failed trial={} code={} reason={}'.format(
                get_current_time(), v.trial_number, v.stim_trigger_code, reason
            )
        )
        goto_state('stopped')


# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    validate_stim_trigger_mode()

    print('{}, movement_triggered_stim_task_started'.format(get_current_time()))
    print('{}, session_duration'.format(v.session_duration))
    print('{}, intertrial_duration'.format(v.intertrial_duration))
    print('{}, motion_wait_time'.format(v.motion_wait_time))
    print('{}, motion_threshold'.format(v.motion_threshold))
    print('{}, stim_trigger_mode={}'.format(get_current_time(), v.stim_trigger_mode))
    print('{}, stim_required_motion_events={}'.format(get_current_time(), v.stim_required_motion_events))
    print('{}, stim_motion_delay_ms={}'.format(get_current_time(), stim_delay_ms()))
    print('{}, stim_timeout'.format(v.stim_timeout))

    set_stim_sync(False)

    if hasattr(hw, 'motionSensor'):
        hw.motionSensor.record()
        hw.motionSensor.threshold = v.motion_threshold
        if hasattr(hw.motionSensor, 'sensor_x') and hw.motionSensor.sensor_x:
            v.cpi = hw.motionSensor.sensor_x.CPI
        print('{}, CPI'.format(v.cpi))
        print('{}, motion_sensor_started'.format(get_current_time()))
    else:
        print('{}, missing_motion_sensor'.format(get_current_time()))

    if hasattr(hw, 'cameraTrigger'):
        hw.cameraTrigger.start()
        print('{}, camera_trigger_started'.format(get_current_time()))
    else:
        print('{}, missing_camera_trigger'.format(get_current_time()))

    if hasattr(hw, 'bci_link'):
        hw.bci_link.notify_on_change = False
        hw.bci_link.start()
        print('{}, bci_link_started'.format(get_current_time()))
        send_to_stim(v.code_session_marker_to_stim)
        print(
            '{}, sent_session_marker_to_stim code={} phase=start'.format(
                get_current_time(), v.code_session_marker_to_stim
            )
        )
    else:
        print('{}, missing_bci_link'.format(get_current_time()))

    set_timer('session_timer', v.session_duration)


def run_end():
    print_summary()
    set_stim_sync(False)

    if hasattr(hw, 'cameraTrigger'):
        hw.cameraTrigger.stop()
        print('{}, camera_trigger_stopped'.format(get_current_time()))

    if hasattr(hw, 'motionSensor'):
        hw.motionSensor.off()
        hw.motionSensor.stop()
        print('{}, motion_sensor_stopped'.format(get_current_time()))

    if hasattr(hw, 'bci_link'):
        send_to_stim(v.code_session_marker_to_stim)
        print(
            '{}, sent_session_marker_to_stim code={} phase=end'.format(
                get_current_time(), v.code_session_marker_to_stim
            )
        )
        hw.bci_link.stop()
        print('{}, bci_link_stopped'.format(get_current_time()))

    hw.off()
    print('{}, movement_triggered_stim_task_ended'.format(get_current_time()))


# -------------------------------------------------------------------------
# State Machine
# -------------------------------------------------------------------------
def intertrial(event):
    if event == 'entry':
        reset_trial_tracking()
        v.motion_detected = False
        v.intertrial_start_time = get_current_time()
        print('{}, intertrial_entry'.format(get_current_time()))
        set_timer('state_timer', v.intertrial_duration, True)

    elif event == 'motion':
        v.motion_detected = True
        v.motion_count += 1
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        time_in_intertrial = get_current_time() - v.intertrial_start_time
        if time_in_intertrial >= v.intertrial_duration:
            if not v.motion_detected:
                goto_state('trial')
            else:
                v.motion_detected = False
                set_timer('state_timer', v.motion_wait_time, True)
        else:
            set_timer('state_timer', v.motion_wait_time, True)

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')


def trial(event):
    if event == 'entry':
        v.trial_number += 1
        v.motion_events_this_trial = 0
        v.first_motion_seen = False
        v.stim_sent_this_trial = False
        v.awaiting_stim_offset = False
        v.stim_active = False
        disarm_timer('stim_delay_timer')
        disarm_timer('stim_timeout_timer')
        print('{}, trial_entry trial={}'.format(get_current_time(), v.trial_number))

    elif event == 'motion':
        v.motion_count += 1
        v.motion_events_this_trial += 1
        v.last_motion_time = get_current_time()

        if v.awaiting_stim_offset or v.stim_sent_this_trial:
            return

        if not v.first_motion_seen:
            v.first_motion_seen = True
            print(
                '{}, first_motion trial={} motion_events={}'.format(
                    get_current_time(), v.trial_number, v.motion_events_this_trial
                )
            )
            if v.stim_trigger_mode == 'first_motion_delay':
                if v.stim_motion_delay <= 0:
                    trigger_stim('first_motion_delay')
                else:
                    set_timer('stim_delay_timer', v.stim_motion_delay)
                    print(
                        '{}, stim_delay_started trial={} delay_ms={}'.format(
                            get_current_time(), v.trial_number, stim_delay_ms()
                        )
                    )

        if (
            v.stim_trigger_mode == 'motion_event_count'
            and v.motion_events_this_trial >= int(v.stim_required_motion_events)
        ):
            trigger_stim('motion_event_count')

    elif event == 'stim_delay_timer':
        if not v.stim_sent_this_trial:
            trigger_stim('first_motion_delay')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')
        disarm_timer('stim_delay_timer')
        disarm_timer('stim_timeout_timer')


def stopped(event):
    if event == 'entry':
        print('{}, stopped_entry'.format(get_current_time()))
        disarm_timer('state_timer')
        disarm_timer('stim_delay_timer')
        disarm_timer('stim_timeout_timer')
        set_stim_sync(False)

    elif event == 'stop_button':
        goto_state('intertrial')


# -------------------------------------------------------------------------
# Global Event Handler
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'cursor_update':
        if hasattr(hw, 'bci_link'):
            name = log_marker(hw.bci_link.spk)
            if name == 'stim_off' and v.awaiting_stim_offset:
                disarm_timer('stim_timeout_timer')
                v.awaiting_stim_offset = False
                v.stim_sent_this_trial = False
                print(
                    '{}, stim_offset_received trial={} markers={}'.format(
                        get_current_time(), v.trial_number, v.marker_count
                    )
                )
                goto_state('intertrial')
        else:
            print('{}, cursor_update_without_bci_link'.format(get_current_time()))
        return True

    if event == 'stim_timeout_timer':
        if v.awaiting_stim_offset:
            v.stim_timeout_count += 1
            print(
                '{}, stim_timeout trial={} timeout_count={}'.format(
                    get_current_time(), v.trial_number, v.stim_timeout_count
                )
            )
            print_summary()
            goto_state('stopped')
        return True

    if event == 'session_timer':
        print('{}, session_timer_expired'.format(get_current_time()))
        print_summary()
        stop_framework()
        return True

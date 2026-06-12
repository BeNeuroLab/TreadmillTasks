"""Receive manual stimulation markers and camera-sync behavior/video."""

from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'intertrial',
    'trial',
]

events = [
    'session_timer',
    'cursor_update',
    'state_timer',
]

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
v.session_duration = 60 * minute

v.marker_count = 0
v.stim_on_count = 0
v.stim_off_count = 0
v.stim_pulse_count = 0
v.unknown_marker_count = 0
v.stim_active = False

# These codes must match cl_stim/config.toml [pycontrol_events.codes].
v.code_stim_on = 101
v.code_stim_off = 102
v.code_stim_pulse = 103
v.code_session_start = 110
v.code_session_end = 111
v.code_session_marker_to_stim = 0

# UARTlink emits cursor_update only when the received integer changes.
# Repeated identical marker codes may not be logged unless the sender
# alternates codes, e.g. stim_on then stim_off for train-mode pulses.

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def marker_name(code):
    if code == v.code_stim_on:
        return 'stim_on'
    if code == v.code_stim_off:
        return 'stim_off'
    if code == v.code_stim_pulse:
        return 'stim_pulse'
    if code == v.code_session_start:
        return 'session_start'
    if code == v.code_session_end:
        return 'session_end'
    return 'unknown'


def update_marker_counts(name):
    v.marker_count += 1

    if name == 'stim_on':
        v.stim_on_count += 1
        v.stim_active = True
    elif name == 'stim_off':
        v.stim_off_count += 1
        v.stim_active = False
    elif name == 'stim_pulse':
        v.stim_pulse_count += 1
        v.stim_active = False
    elif name == 'unknown':
        v.unknown_marker_count += 1


def log_marker(code):
    name = marker_name(code)
    update_marker_counts(name)
    print(
        '{}, external_stim_marker code={} name={} count={} active={}'.format(
            get_current_time(),
            code,
            name,
            v.marker_count,
            v.stim_active,
        )
    )


def print_summary():
    print(
        '{}, external_stim_summary total={} stim_on={} stim_off={} '
        'stim_pulse={} unknown={} active={}'.format(
            get_current_time(),
            v.marker_count,
            v.stim_on_count,
            v.stim_off_count,
            v.stim_pulse_count,
            v.unknown_marker_count,
            v.stim_active,
        )
    )


def send_session_marker_to_stim(phase):
    hw.bci_link.send_int_to_bci(v.code_session_marker_to_stim)
    print(
        '{}, sent_session_marker_to_stim code={} phase={}'.format(
            get_current_time(),
            v.code_session_marker_to_stim,
            phase,
        )
    )


# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    print('{}, manual_stim_receiver_started'.format(get_current_time()))
    print('{}, session_duration'.format(v.session_duration))

    if hasattr(hw, 'bci_link'):
        hw.bci_link.start()
        print('{}, bci_link_started'.format(get_current_time()))
        send_session_marker_to_stim('start')
    else:
        print('{}, missing_bci_link'.format(get_current_time()))

    if hasattr(hw, 'cameraTrigger'):
        hw.cameraTrigger.start()
        print('{}, camera_trigger_started'.format(get_current_time()))
    else:
        print('{}, missing_camera_trigger'.format(get_current_time()))

    set_timer('session_timer', v.session_duration, True)


def run_end():
    print_summary()

    if hasattr(hw, 'cameraTrigger'):
        hw.cameraTrigger.stop()
        print('{}, camera_trigger_stopped'.format(get_current_time()))

    if hasattr(hw, 'bci_link'):
        send_session_marker_to_stim('end')
        hw.bci_link.stop()
        print('{}, bci_link_stopped'.format(get_current_time()))

    print('{}, manual_stim_receiver_ended'.format(get_current_time()))


# -------------------------------------------------------------------------
# State Machine
# -------------------------------------------------------------------------
def intertrial(event):
    if event == 'entry':
        print('{}, receiver_intertrial_entry'.format(get_current_time()))
        timed_goto_state('trial', 1 * ms)


def trial(event):
    if event == 'entry':
        print('{}, receiver_trial_entry'.format(get_current_time()))

    elif event == 'cursor_update':
        if hasattr(hw, 'bci_link'):
            log_marker(hw.bci_link.spk)
        else:
            print('{}, cursor_update_without_bci_link'.format(get_current_time()))


def all_states(event):
    if event == 'session_timer':
        print('{}, session_timer_expired'.format(get_current_time()))
        print_summary()
        stop_framework()

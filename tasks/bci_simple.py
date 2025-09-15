# ===== Timer-lite BCI task (no stop button) =====
from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math

# -------------------------------------------------------------------------
# States / Events (reduced)
# -------------------------------------------------------------------------
states = ['intertrial', 'trial', 'reward']
events  = [
    'session_timer',
    'motion',
    'cursor_update',
    'lick',
    'quiescence_timer',
]
initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Parameters
# -------------------------------------------------------------------------
# Session
v.session_duration      = 60 * minute

# ITI / gating
v.intertrial_duration   = 3 * second     # minimum ITI
v.motion_wait_time      = 1 * second     # must be this long without motion
v.baseline_freq_hz      = 4000           # BCI must be <= this before starting trial

# Trial
v.trial_timeout         = 15 * second    # max trial length
v.hold_time             = 0.12 * second  # must keep freq >= goal this long for success

# Reward
v.reward_window         = 5 * second     # lick window (uses timed_goto_state)
v.reward_duration       = 40 * ms

# Audio / BCI
v.start_freq_hz         = 2000
v.goal_freq_hz          = 12000

# Motion sensor
v.cpi                   = 100
v.motion_threshold      = 2

# Tracking
v.reward_number         = 0
v.last_motion_time      = 0
v.intertrial_entry_time = 0
v.bci_freq              = v.start_freq_hz
v.is_holding            = False
v.hold_deadline         = 0
v.first_motion_sent     = False

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def reset_trial_vars():
    v.bci_freq      = v.start_freq_hz
    v.is_holding    = False
    v.hold_deadline = 0
    v.first_motion_sent = False

def arm_quiescence_check():
    """
    Single self-rearming timer to gate intertrial exit.
    Conditions to start trial:
      (1) ITI >= v.intertrial_duration
      (2) No motion for >= v.motion_wait_time
      (3) v.bci_freq <= v.baseline_freq_hz
    """
    now = get_current_time()
    need_iti   = max(0, v.intertrial_duration - (now - v.intertrial_entry_time))
    need_quiet = max(0, v.motion_wait_time     - (now - v.last_motion_time))
    have_bci   = (v.bci_freq <= v.baseline_freq_hz)

    if (need_iti == 0) and (need_quiet == 0) and have_bci:
        goto_state('trial')
    else:
        delay = max(need_iti, need_quiet, 100)  # >=100 ms to keep CPU load low
        set_timer('quiescence_timer', delay, True)

# -------------------------------------------------------------------------
# Run start/end
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(15)
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_threshold
    hw.reward.reward_duration = v.reward_duration
    hw.bci_link.start()
    hw.light.start()
    hw.light.off()

    v.last_motion_time = get_current_time()

    if hasattr(hw.motionSensor, 'sensor_x'):
        v.cpi = hw.motionSensor.sensor_x.CPI

    print('{}, CPI'.format(v.cpi))
    print('{}, motion_threshold'.format(v.motion_threshold))
    print('{}, motion_wait_time'.format(v.motion_wait_time))
    print('{}, trial_timeout'.format(v.trial_timeout))
    print('{}, hold_time'.format(v.hold_time))
    print('{}, baseline_frequency'.format(v.baseline_freq_hz))
    print('{}, goal_frequency'.format(v.goal_freq_hz))
    print('{}, before_camera_trigger'.format(get_current_time()))

    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration, True)

def run_end():
    hw.speaker.off()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.light.off()
    hw.bci_link.stop()
    hw.cameraTrigger.stop()
    hw.off()
    print('Session Ended')

# -------------------------------------------------------------------------
# States
# -------------------------------------------------------------------------
def intertrial(event):
    """
    Start a new trial when:
      - minimum ITI elapsed,
      - no motion for v.motion_wait_time,
      - BCI baseline at/below v.baseline_freq_hz.
    """
    if event == 'entry':
        hw.speaker.off()
        reset_trial_vars()
        now = get_current_time()
        v.intertrial_entry_time = now
        v.last_motion_time = now
        arm_quiescence_check()

    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'cursor_update':
        # Track BCI baseline; fast-path into trial if all conditions are satisfied.
        bci_val = hw.bci_link.spk
        if bci_val is not None:
            v.bci_freq = bci_val
            now = get_current_time()
            if ((now - v.intertrial_entry_time) >= v.intertrial_duration and
                (now - v.last_motion_time)    >= v.motion_wait_time     and
                v.bci_freq <= v.baseline_freq_hz):
                goto_state('trial')

    elif event == 'quiescence_timer':
        arm_quiescence_check()

    elif event == 'exit':
        disarm_timer('quiescence_timer')

def trial(event):
    """
    Hold v.bci_freq >= v.goal_freq_hz for v.hold_time to succeed.
    Trial auto-times out via timed_goto_state (no named trial_timer).
    """
    if event == 'entry':
        hw.speaker.sine(v.start_freq_hz)
        v.is_holding = False
        v.hold_deadline = 0
        timed_goto_state('intertrial', v.trial_timeout)
        print('trial_start')

    elif event == 'motion':
        if not v.first_motion_sent:
            v.first_motion_sent = True

    elif event == 'cursor_update':
        val = hw.bci_link.spk
        if val is None:
            return
        v.bci_freq = val
        hw.speaker.sine(v.bci_freq)

        now = get_current_time()
        if v.bci_freq >= v.goal_freq_hz:
            if not v.is_holding:
                v.is_holding = True
                v.hold_deadline = now + v.hold_time
            else:
                if now >= v.hold_deadline:
                    goto_state('reward')
        else:
            if v.is_holding:
                v.is_holding = False
                v.hold_deadline = 0

    elif event == 'exit':
        hw.speaker.off()

def reward(event):
    """
    Reward state. Delivers water upon lick within v.reward_window.
    """
    if event == 'entry':
        print('reward_entered')
        timed_goto_state('intertrial', v.reward_window)

    elif event == 'lick':
        v.reward_number += 1
        # hw.reward.release()  # uncomment to deliver water
        hw.speaker.off()
        print('{}, reward_number'.format(v.reward_number))
        goto_state('intertrial')

# -------------------------------------------------------------------------
# Global handler
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'session_timer':
        print('Session Timer Expired')
        print('{}, total_rewards'.format(v.reward_number))
        stop_framework()

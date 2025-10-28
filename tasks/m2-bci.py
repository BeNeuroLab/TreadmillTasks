"""
M2 BCI task

Oct 22nd 2025
"""

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'intertrial',
    'trial',
    'reward',
]

events = [
    'session_timer',
    'motion',              # Motion events from sensor
    'cursor_update',       # BCI frequency updates
    'lick',
    'trial_timer',         # Trial timeout
    'motion_check_timer',  # Timer to check for trial start conditions
    'hold_timer',          # NEW: Timer for holding frequency at target
]

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session parameters
v.session_duration = 60 * minute

# Trial parameters
v.intertrial_duration = 3 * second   # Minimum time between trials
v.trial_timeout = 15 * second        # Max time to reach target frequency
v.motion_wait_time = 1 * second      # Time without motion before trial can start
v.reward_duration = 40 * ms
v.reward_state_duration = 3 * second   # Time to remain in reward state before intertrial

# BCI Parameters
v.hold_time = 0.12 * second          # Time freq must be >= target for reward
v.baseline_freq_hz = 4000            # Freq must be <= this to start a trial
v.goal_freq_hz = 10000               # Target frequency (Hz)
v.start_freq_hz = 2000               # Starting frequency (Hz)

# Motion sensor parameters
v.cpi = 100                          # Counts per inch (will be updated from sensor)
v.motion_threshold = 2               # Motion event threshold

# Trial tracking
v.reward_number = 0
v.last_motion_time = 0               # Track when last motion occurred
v.first_motion_sent = False          # Flag to track if first motion event was sent to BCI
v.last_lick_time = 0                 # Track when last lick occurred

# BCI variables
v.bci_freq = v.start_freq_hz         # Frequency received from BCI
v.is_holding = False                 # Flag to indicate if hold timer is active

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------
def reset_trial():
    """Reset variables for a new trial."""
    v.bci_freq = v.start_freq_hz
    v.first_motion_sent = False
    v.is_holding = False

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(10)
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_threshold
    hw.reward.reward_duration = v.reward_duration
    hw.bci_link.start()
    hw.light.start()
    hw.light.off()
    # Initialize last_motion_time at the start of the session
    v.last_motion_time = get_current_time()
    v.last_lick_time = v.last_motion_time
    
    # Get actual CPI from sensor
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
    hw.bci_link.stop() # Stop the BCI UART link
    hw.cameraTrigger.stop()
    hw.off()
    print('Session Ended')

def trial(event):
    """
    During trial, provide continuous auditory feedback of BCI frequency.
    Mouse must hold frequency >= goal for v.hold_time to earn reward.
    Any lick or motion aborts the trial to intertrial.
    """
    if event == 'entry':
        hw.speaker.sine(v.start_freq_hz)
        set_timer('trial_timer', v.trial_timeout, True)
        print('trial_start')

    elif event == 'exit':
        disarm_timer('trial_timer')
        disarm_timer('hold_timer')
        v.is_holding = False

    elif event == 'motion' or event == 'lick':
        # Abort trial on any movement or lick
        goto_state('intertrial')

    elif event == 'cursor_update':
        # Update frequency from BCI and provide feedback
        bci_val = hw.bci_link.spk
        if bci_val is not None:
            v.bci_freq = bci_val
            print('{}, freq'.format(v.bci_freq))
            hw.speaker.sine(v.bci_freq)

            # Manage hold logic
            if v.bci_freq >= v.goal_freq_hz:
                if not v.is_holding:
                    set_timer('hold_timer', v.hold_time, True)
                    v.is_holding = True
            else:
                if v.is_holding:
                    disarm_timer('hold_timer')
                    v.is_holding = False

    elif event == 'hold_timer':
        # Successful hold earns reward
        goto_state('reward')

    elif event == 'trial_timer':
        # Trial timed out without reward; return to intertrial
        goto_state('intertrial')

def intertrial(event):
    """
    Start a trial only if:
    - At least v.intertrial_duration has elapsed.
    - No motion and no lick for v.motion_wait_time.
    - BCI frequency is back to baseline (<= v.baseline_freq_hz).
    """
    if event == 'entry':
        hw.speaker.off()
        reset_trial()
        # Start checking for start conditions after min intertrial duration
        set_timer('motion_check_timer', v.intertrial_duration, True)

    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'lick':
        v.last_lick_time = get_current_time()

    elif event == 'cursor_update':
        bci_val = hw.bci_link.spk
        if bci_val is not None:
            v.bci_freq = bci_val
            print('{}, freq'.format(v.bci_freq))

    elif event == 'motion_check_timer':
        now = get_current_time()
        no_motion = (now - v.last_motion_time) >= v.motion_wait_time
        no_lick = (now - v.last_lick_time) >= v.motion_wait_time
        baseline = v.bci_freq <= v.baseline_freq_hz

        if no_motion and no_lick and baseline:
            goto_state('trial')
        else:
            set_timer('motion_check_timer', 200 * ms, True)

def reward(event):
    """
    Deliver reward immediately on entry, then return to intertrial.
    """
    if event == 'entry':
        timed_goto_state('intertrial', v.reward_state_duration)
    elif event == "motion":
        goto_state('intertrial')
    elif event == 'lick':
        v.reward_number += 1
        hw.reward.release()
        hw.speaker.off()
        print('{}, reward_number'.format(v.reward_number))
        goto_state('intertrial')
    # No additional handling needed; transition scheduled by timed_goto_state

# -------------------------------------------------------------------------
# Event handlers
# -------------------------------------------------------------------------
def all_states(event):
    """
    Generic event handler for events that can occur in any state.
    """
    if event == 'session_timer':
        print('Session Timer Expired')
        print('{}, total_rewards'.format(v.reward_number))
        stop_framework()

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
    'stopped'
]

events = [
    'session_timer',
    'motion',              # Motion events from sensor
    'cursor_update',       # BCI frequency updates
    'lick',
    'trial_timer',         # Trial timeout
    'reward_timer',        # Timer for lick window
    'motion_check_timer',  # Timer to check for trial start conditions
    'hold_timer',          # NEW: Timer for holding frequency at target
    'stop_button'
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

# --- NEW/MODIFIED BCI Parameters ---
v.hold_time = 0.12 * second           # REQUIRED: Time freq must be >= target for reward
v.baseline_freq_hz = 4000            # REQUIRED: Freq must be <= this to start a trial
v.goal_freq_hz = 12000               # Target frequency (Hz)
v.start_freq_hz = 2000               # Starting frequency (Hz)

# Motion sensor parameters
v.cpi = 100                          # Counts per inch (will be updated from sensor)
v.motion_threshold = 10              # Motion event threshold

# Trial tracking
v.reward_number = 0
v.last_motion_time = 0               # Track when last motion occurred
v.first_motion_sent = False          # Flag to track if first motion event was sent to BCI

# BCI variables
v.bci_freq = v.start_freq_hz         # Frequency received from BCI
v.is_holding = False                 # NEW: Flag to indicate if hold timer is active

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------
def reset_trial():
    """Reset variables for a new trial"""
    v.bci_freq = v.start_freq_hz
    v.first_motion_sent = False
    v.is_holding = False

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(15)
    hw.bci_link.start()
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_threshold
    hw.reward.reward_duration = v.reward_duration
    hw.light.start()
    hw.light.off()
    # Initialize last_motion_time at the start of the session
    v.last_motion_time = get_current_time()
    
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
    hw.light.off()
    hw.motionSensor.stop()
    hw.motionSensor.off()
    hw.bci_link.stop() # Stop the BCI UART link
    hw.cameraTrigger.stop()
    hw.off()
    print('Session Ended')

# -------------------------------------------------------------------------
# State Machine
# -------------------------------------------------------------------------
def intertrial(event):
    """
    Waits for the conditions to start a new trial:
    1. Minimum intertrial duration has passed.
    2. No motion for `v.motion_wait_time`.
    3. BCI frequency is at or below `v.baseline_freq_hz`.
    """
    if event == 'entry':
        hw.speaker.off()
        reset_trial()
        # Start checking for trial start conditions after the min intertrial duration.
        set_timer('motion_check_timer', v.intertrial_duration, True)
        
    elif event == 'cursor_update':
        # Keep track of BCI frequency during the intertrial period.
        bci_val = hw.bci_link.spk 
        if bci_val is not None:
            v.bci_freq = bci_val
            print('{}, freq'.format(v.bci_freq))
            
    elif event == 'motion':
        # Update the timestamp of the last detected movement.
        v.last_motion_time = get_current_time()
        
    elif event == 'motion_check_timer':
        time_since_motion = get_current_time() - v.last_motion_time
        
        # Check if all conditions to start a new trial are met.
        if (time_since_motion >= v.motion_wait_time and
                v.bci_freq <= v.baseline_freq_hz):
            goto_state('trial')
        else:
            # If conditions are not met, check again shortly.
            set_timer('motion_check_timer', 200 * ms, True)
    
    elif event == 'stop_button':
        goto_state('stopped')

def trial(event):
    """
    The mouse attempts to hold the BCI frequency at or above the target
    for a specified hold time to get a reward.
    """
    if event == 'entry':
        hw.speaker.sine(v.start_freq_hz)
        set_timer('trial_timer', v.trial_timeout, True)
        print('trial_start')
        
    elif event == 'exit':
        disarm_timer('trial_timer')
        disarm_timer('hold_timer') # Ensure hold_timer is stopped on exit
        v.is_holding = False
        
    elif event == 'motion':
        # Send first motion signal to BCI
        if not v.first_motion_sent:
            v.first_motion_sent = True
            print('first_motion_sent_to_BCI')
            
    elif event == 'cursor_update':
        # Receive frequency from BCI
        v.bci_freq = hw.bci_link.spk
        if v.bci_freq is not None:
            # Provide continuous auditory feedback.
            print('{}, freq'.format(v.bci_freq))
            hw.speaker.sine(v.bci_freq)
            
            # Check if frequency is high enough to start/maintain the hold.
            if v.bci_freq >= v.goal_freq_hz:
                if not v.is_holding:
                    # Start the hold timer if it's not already running.
                    set_timer('hold_timer', v.hold_time, True)
                    v.is_holding = True
                    print('{}, hold_started'.format(get_current_time()))
            else:
                # If frequency drops, reset the hold.
                if v.is_holding:
                    disarm_timer('hold_timer')
                    v.is_holding = False
                    print('{}, hold_reset'.format(get_current_time()))

    elif event == 'hold_timer':
        # Fired if the frequency was held high for the entire hold_time.
        print('{}, hold_success'.format(get_current_time()))
        goto_state('reward')
        
    elif event == 'trial_timer':
        # Trial timeout - failed to reach target.
        goto_state('intertrial')
        
    elif event == 'stop_button':
        goto_state('stopped')

def reward(event):
    """
    Reward state. Delivers water upon lick.
    """
    if event == 'entry':
        set_timer('reward_timer', 5*second, True)  # 5 seconds to lick for reward
        print('reward_state_entered')
        
    elif event == 'exit':
        disarm_timer('reward_timer')
        
    elif event == 'lick':
        v.reward_number += 1
        hw.reward.release()
        hw.speaker.off()
        print('{}, reward_number'.format(v.reward_number))
        goto_state('intertrial') # Go directly to intertrial to start the cycle again
        
    elif event == 'reward_timer':
        # No lick within the timeout window.
        goto_state('intertrial')
    
    elif event == 'stop_button':
        goto_state('stopped')

def stopped(event):
    """
    Stops all timers and hardware when the stop button is pressed.
    """
    if event == 'entry':
        hw.speaker.off()
        # Disarm all potentially running timers.
        disarm_timer('motion_check_timer')
        disarm_timer('trial_timer')
        disarm_timer('reward_timer')
        disarm_timer('hold_timer')
        
    elif event == 'stop_button':
        # Pressing stop again resumes the task.
        goto_state('intertrial')

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

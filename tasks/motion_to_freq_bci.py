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
    'motion',        # Motion events from sensor
    'cursor_update', # BCI frequency updates
    'lick',
    'trial_start',
    'trial_timer',
    'reward_timer',
    'motion_check_timer',
    'target_tone_timer',  # Timer for goal frequency playback
    'stop_button'
]

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session parameters
v.session_duration = 30 * minute

# Trial parameters
v.intertrial_duration = 4 * second
v.trial_timeout = 15 * second       # Max time to reach target frequency
v.motion_wait_time = 2 * second     # Time without motion before trial can start
v.reward_duration = 30 * ms
v.target_present_duration = 1 * second  # Duration to play goal frequency

# Frequency mapping
v.start_freq_hz = 2000      # Starting frequency (Hz)
v.goal_freq_hz = 12000       # Goal frequency (Hz)

# Discrete frequency steps
v.num_steps = 5            # Number of discrete frequency steps (like semitones)
v.current_step = 0          # Current frequency step
v.current_freq = v.start_freq_hz

# Motion sensor parameters
v.cpi = 100                 # Counts per inch (will be updated from sensor)
v.motion_threshold = 10     # Motion event threshold

# Trial tracking
v.reward_number = 0
v.last_motion_time = 0      # Track when last motion occurred
v.motion_detected = False   # Flag for motion during wait period
v.intertrial_start_time = 0 # Track when intertrial started
v.first_motion_sent = False # Flag to track if first motion event was sent to BCI

# BCI variables
v.bci_freq = v.start_freq_hz  # Frequency received from BCI
v.last_bci_freq = v.start_freq_hz  # Track last BCI frequency to detect changes
v.speaker_freq = v.start_freq_hz  # Current frequency playing on speaker

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------
def get_octave_boundaries(freq):
    """Get the lower and upper boundaries of the octave containing freq"""
    # Find the octave that contains this frequency
    lower_boundary = 2 ** math.floor(math.log2(freq))
    upper_boundary = lower_boundary * 2
    return lower_boundary, upper_boundary

def crosses_octave_boundary(old_freq, new_freq):
    """Check if frequency crosses an octave boundary"""
    old_lower, _ = get_octave_boundaries(old_freq)
    new_lower, _ = get_octave_boundaries(new_freq)
    
    # Update if we've moved to a different octave
    return old_lower != new_lower

def update_frequency_from_bci(bci_freq):
    """Update speaker frequency based on BCI input, only when crossing octave boundaries"""
    if bci_freq is None:
        return False
    
    # Check if this crosses an octave boundary compared to current speaker frequency
    if crosses_octave_boundary(v.speaker_freq, bci_freq):
        v.speaker_freq = bci_freq
        hw.speaker.sine(v.speaker_freq)
        print('{}, frequency_updated'.format(v.speaker_freq))
        
        # Check if we've reached the goal
        if bci_freq >= v.goal_freq_hz:
            # Play goal frequency and then go to reward
            hw.speaker.sine(v.goal_freq_hz)
            print('{}, target_reached'.format(v.goal_freq_hz))
            set_timer('target_tone_timer', v.target_present_duration, True)
            return True
    
    return False

def reset_trial():
    """Reset variables for a new trial"""
    v.current_step = 0
    v.current_freq = v.start_freq_hz
    v.bci_freq = v.start_freq_hz
    v.last_bci_freq = v.start_freq_hz
    v.speaker_freq = v.start_freq_hz
    v.motion_detected = False
    v.first_motion_sent = False

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(15)
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_threshold
    hw.reward.reward_duration = v.reward_duration
    
    # Get actual CPI from sensor
    if hasattr(hw.motionSensor, 'sensor_x'):
        v.cpi = hw.motionSensor.sensor_x.CPI
    
    print('{}, CPI'.format(v.cpi))
    print('{}, motion_threshold'.format(v.motion_threshold))
    print('{}, motion_wait_time'.format(v.motion_wait_time))
    print('{}, trial_timeout'.format(v.trial_timeout))
    print('{}, start_frequency'.format(v.start_freq_hz))
    print('{}, goal_frequency'.format(v.goal_freq_hz))
    print('{}, num_steps'.format(v.num_steps))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration, True)

def run_end():
    hw.speaker.off()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.off()
    print('Session Ended')

# -------------------------------------------------------------------------
# State Machine
# -------------------------------------------------------------------------
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        hw.bci_link.send_int(4)  # Send trial end signal to BCI
        reset_trial()
        v.motion_detected = False
        v.intertrial_start_time = get_current_time()
        # Start checking for motion after minimum intertrial duration
        set_timer('motion_check_timer', v.intertrial_duration, True)
        
    elif event == 'motion':
        v.motion_detected = True
        v.last_motion_time = get_current_time()
        
    elif event == 'motion_check_timer':
        # Check if we've been in intertrial for at least intertrial_duration
        time_in_intertrial = get_current_time() - v.intertrial_start_time
        if time_in_intertrial >= v.intertrial_duration:
            if not v.motion_detected:
                # No motion detected for required duration, start trial
                goto_state('trial')
            else:
                # Motion was detected, reset timer and try again
                v.motion_detected = False
                set_timer('motion_check_timer', v.motion_wait_time, True)
        else:
            # Haven't reached minimum intertrial duration yet
            set_timer('motion_check_timer', v.motion_wait_time, True)
    
    elif event == 'stop_button':
        goto_state('stopped')

def trial(event):
    if event == 'entry':
        hw.bci_link.send_int(1)  # Send trial start signal to BCI
        hw.speaker.sine(v.start_freq_hz)
        set_timer('trial_timer', v.trial_timeout, True)
        print('trial_start')
        
    elif event == 'exit':
        disarm_timer('trial_timer')
        
    elif event == 'motion':
        # Send first motion signal to BCI
        if not v.first_motion_sent:
            hw.bci_link.send_int(2)
            v.first_motion_sent = True
            print('first_motion_sent_to_BCI')
        
    elif event == 'cursor_update':
        # Receive frequency from BCI
        v.bci_freq = hw.bci_link.spk
        if v.bci_freq is not None:
            print('{}, cursor_update_freq'.format(v.bci_freq))
            
            # Update speaker frequency only if crossing octave boundary
            update_frequency_from_bci(v.bci_freq)
            
            # Store last BCI frequency
            v.last_bci_freq = v.bci_freq
        
    elif event == 'trial_timer':
        # Trial timeout - failed to reach target
        goto_state('intertrial')
    
    elif event == 'target_tone_timer':
        # Goal frequency playback finished, go to reward
        goto_state('reward')
    
    elif event == 'stop_button':
        goto_state('stopped')

def reward(event):
    if event == 'entry':
        hw.bci_link.send_int(3)  # Send reward start signal to BCI
        set_timer('reward_timer', 5*second, True)  # 5 seconds to get reward
        print('reward_state_entered')
        
    elif event == 'exit':
        disarm_timer('reward_timer')
        
    elif event == 'lick':
        v.reward_number += 1
        hw.reward.release()
        hw.speaker.off()
        print('{}, reward_number'.format(v.reward_number))
        set_timer('trial_start', v.intertrial_duration, True)
        goto_state('intertrial')
        
    elif event == 'reward_timer':
        # No lick within timeout
        goto_state('intertrial')
    
    elif event == 'stop_button':
        goto_state('stopped')

def stopped(event):
    if event == 'entry':
        hw.speaker.off()
        disarm_timer('motion_check_timer')
        disarm_timer('trial_timer')
        disarm_timer('reward_timer')
        disarm_timer('target_tone_timer')
    
    elif event == 'stop_button':
        goto_state('intertrial')

# -------------------------------------------------------------------------
# Event handlers
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'session_timer':
        print('Session Timer Expired')
        print('{}, total_rewards'.format(v.reward_number))
        stop_framework()
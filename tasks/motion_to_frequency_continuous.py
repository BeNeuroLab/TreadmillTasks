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
    'lick',
    'session_timer',
    'motion',        # Motion events from sensor
    'trial_begin',
    'trial_timer',
    'reward_timer',
    'motion_check_timer',
]

initial_state = 'trial'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session parameters
v.session_duration = 3 * minute

# Trial parameters
v.intertrial_duration = 4 * second
v.trial_timeout = 15 * second       # Max time to reach target frequency
v.motion_wait_time = 1 * second     # Time without motion before trial can start
v.reward_duration = 40 * ms
v.target_present_duration = 1 * second  # Duration to play goal frequency

# Distance and frequency mapping
v.goal_distance = 30       # Distance units to reach goal frequency
v.current_distance = 0       # Accumulated distance traveled
v.start_freq_hz = 2000      # Starting frequency (Hz)
v.goal_freq_hz = 12000       # Goal frequency (Hz)

# Discrete frequency steps
v.num_steps = 3            # Number of discrete frequency steps (like semitones)
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

v.first_trial = 1

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------
def calculate_frequency_for_step(step):
    """Calculate frequency for a given step using log scale (octaves)"""
    # Calculate number of octaves between start and goal frequencies
    octaves = math.log2(v.goal_freq_hz / v.start_freq_hz)
    
    # Calculate frequency for this step
    # Each step represents a fraction of the total octave range
    step_fraction = step / v.num_steps
    freq_multiplier = 2 ** (octaves * step_fraction)
    
    return int(v.start_freq_hz * freq_multiplier)

def update_frequency_from_distance():
    """Update frequency based on current distance traveled"""
    # Calculate progress as fraction of goal distance
    progress = min(v.current_distance / v.goal_distance, 1.0)
    
    # Calculate which discrete step we should be at
    new_step = int(progress * v.num_steps)
    
    # Only update frequency if we've moved to a new step
    if new_step != v.current_step:
        v.current_step = new_step
        v.current_freq = calculate_frequency_for_step(v.current_step)
        hw.speaker.sine(v.current_freq)
        
        print('{}, distance'.format(v.current_distance))
        print('{}, frequency'.format(v.current_freq))
        
        # Check if we've reached the goal
        if v.current_distance >= v.goal_distance:
            # Play goal frequency and then go to reward
            hw.speaker.sine(v.goal_freq_hz)
            print('{}, target_reached'.format(v.goal_freq_hz))
            timed_goto_state('reward',v.target_present_duration)

def reset_trial():
    """Reset variables for a new trial"""
    v.current_distance = 0
    v.current_step = 0
    v.current_freq = v.start_freq_hz
    v.motion_detected = False

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(15)
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_threshold
    hw.reward.reward_duration = v.reward_duration
    hw.light.start()
    hw.light.off()
    # Get actual CPI from sensor
    if hasattr(hw.motionSensor, 'sensor_x'):
        v.cpi = hw.motionSensor.sensor_x.CPI
    
    #print('{}, CPI'.format(v.cpi))
    print('{}, motion_threshold'.format(v.motion_threshold))
    print('{}, motion_wait_time'.format(v.motion_wait_time))
    print('{}, trial_timeout'.format(v.trial_timeout))
    print('{}, start_frequency'.format(v.start_freq_hz))
    print('{}, goal_frequency'.format(v.goal_freq_hz))
    print('{}, goal_distance'.format(v.goal_distance))
    print('{}, num_steps'.format(v.num_steps))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration, True)

def run_end():
    hw.light.off()
    hw.speaker.off()
    hw.reward.stop()
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
        reset_trial()
        v.motion_detected = False
        v.intertrial_start_time = get_current_time()
        # Start checking for motion after minimum intertrial duration

        if v.first_trial == 1:
            set_timer('motion_check_timer', 30 * second, True)
            v.first_trial = 0
        else:
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


def trial(event):
    if event == 'entry':
        hw.speaker.sine(v.start_freq_hz)
        set_timer('trial_timer', v.trial_timeout, True)
        
    elif event == 'exit':
        disarm_timer('trial_timer')
        
    elif event == 'motion':
        # Motion event fired - accumulate distance
        v.current_distance += v.motion_threshold
        
        # Update frequency based on new distance
        update_frequency_from_distance()
        
    elif event == 'trial_timer':
        # Trial timeout - failed to reach target
        goto_state('intertrial')


def reward(event):
    if event == 'entry':
        set_timer('reward_timer', 3*second, True)  # 5 seconds to get reward
        
    elif event == 'exit':
        disarm_timer('reward_timer')
        
    elif event == 'lick':
        v.reward_number += 1
        hw.reward.release()
        hw.speaker.off()
        print('{}, reward_number'.format(v.reward_number))
        set_timer('trial_begin', v.intertrial_duration, True)
        goto_state('intertrial')
        
    elif event == 'reward_timer':
        # No lick within timeout
        goto_state('intertrial')
    



# -------------------------------------------------------------------------
# Event handlers
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'session_timer':
        print('Session Timer Expired')
        print('{}, total_rewards'.format(v.reward_number))
        stop_framework()
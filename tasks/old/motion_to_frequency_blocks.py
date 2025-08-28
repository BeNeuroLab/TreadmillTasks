from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math
import random

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'intertrial',
    'trial_contingent',  # Motion-contingent frequency trials
    'trial_random',      # Random frequency trials
    'reward',
    'stopped'
]

events = [
    'session_timer',
    'block_timer',       # Timer to switch between blocks
    'motion',            # Motion events from sensor
    'lick',
    'trial_start',
    'trial_timer',
    'reward_timer',
    'motion_check_timer',
    'random_tone_timer', # Timer for random tone trials
    'target_tone_timer', # Timer for goal frequency playback
    'stop_button'
]

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session parameters
v.session_duration = 30 * minute

# Block parameters
v.block_duration = 5 * minute      # Duration of each block type
v.current_block = 'contingent'     # Start with contingent block
v.block_number = 0

# Trial parameters
v.intertrial_duration = 5 * second
v.trial_timeout_contingent = 15 * second    # Timeout for contingent trials
v.trial_timeout_random = 5 * second          # Shorter timeout for random trials
v.motion_wait_time = 2 * second              # Time without motion before trial can start
v.reward_duration = 30 * ms
v.target_present_duration = 1 * second       # Duration to play goal frequency

# Distance and frequency mapping for contingent trials
v.goal_distance = 50                # Distance units to reach goal frequency
v.current_distance = 0              # Accumulated distance traveled
v.start_freq_hz = 2000             # Starting frequency (Hz)
v.goal_freq_hz = 12000             # Goal frequency (Hz)

# Discrete frequency steps
v.num_steps = 5                    # Number of discrete frequency steps
v.current_step = 0                 # Current frequency step
v.current_freq = v.start_freq_hz

# Random trial parameters
v.random_frequencies = []          # Will be populated with possible frequencies
v.random_freq_current = v.start_freq_hz

# Motion sensor parameters
v.cpi = 100                        # Counts per inch (will be updated from sensor)
v.motion_threshold = 10            # Motion event threshold

# Trial tracking
v.reward_number = 0
v.contingent_rewards = 0
v.random_rewards = 0
v.last_motion_time = 0             # Track when last motion occurred
v.motion_detected = False          # Flag for motion during wait period
v.intertrial_start_time = 0        # Track when intertrial started

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

def populate_random_frequencies():
    """Populate list of possible frequencies for random trials"""
    v.random_frequencies = []
    for step in range(v.num_steps + 1):  # Include all steps from 0 to num_steps
        freq = calculate_frequency_for_step(step)
        v.random_frequencies.append(freq)

def update_frequency_from_distance():
    """Update frequency based on current distance traveled (contingent trials only)"""
    # Calculate progress as fraction of goal distance
    progress = min(v.current_distance / v.goal_distance, 1.0)
    
    # Calculate which discrete step we should be at
    new_step = int(progress * v.num_steps)
    
    # Only update frequency if we've moved to a new step
    if new_step != v.current_step:
        v.current_step = new_step
        v.current_freq = calculate_frequency_for_step(v.current_step)
        hw.speaker.sine(v.current_freq)
        
        print('{:.1f}, distance'.format(v.current_distance))
        print('{}, frequency'.format(v.current_freq))
        
        # Check if we've reached the goal
        if v.current_distance >= v.goal_distance:
            # Play goal frequency and then go to reward
            hw.speaker.sine(v.goal_freq_hz)
            print('{}, target_reached'.format(v.goal_freq_hz))
            set_timer('target_tone_timer', v.target_present_duration, True)

def reset_trial():
    """Reset variables for a new trial"""
    v.current_distance = 0
    v.current_step = 0
    v.current_freq = v.start_freq_hz
    v.motion_detected = False

def switch_block():
    """Switch between contingent and random blocks"""
    v.block_number += 1
    if v.current_block == 'contingent':
        v.current_block = 'random'
        print('Switching to RANDOM block')
    else:
        v.current_block = 'contingent'
        print('Switching to CONTINGENT block')
    
    print('{}, block_number'.format(v.block_number))
    set_timer('block_timer', v.block_duration, True)

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
    
    # Populate random frequencies
    populate_random_frequencies()
    
    print('{}, CPI'.format(v.cpi))
    print('{}, motion_threshold'.format(v.motion_threshold))
    print('{}, motion_wait_time'.format(v.motion_wait_time))
    print('{}, trial_timeout_contingent'.format(v.trial_timeout_contingent))
    print('{}, trial_timeout_random'.format(v.trial_timeout_random))
    print('{}, start_frequency'.format(v.start_freq_hz))
    print('{}, goal_frequency'.format(v.goal_freq_hz))
    print('{}, goal_distance'.format(v.goal_distance))
    print('{}, num_steps'.format(v.num_steps))
    print('{}, block_duration'.format(v.block_duration))
    print('Starting with CONTINGENT block')
    
    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration, True)
    set_timer('block_timer', v.block_duration, True)

def run_end():
    hw.speaker.off()
    hw.motionSensor.stop()
    hw.motionSensor.off()
    hw.cameraTrigger.stop()
    hw.off()
    print('Session Ended')
    print('{}, total_rewards'.format(v.reward_number))
    print('{}, contingent_rewards'.format(v.contingent_rewards))
    print('{}, random_rewards'.format(v.random_rewards))

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
        set_timer('motion_check_timer', v.intertrial_duration, True)
        
    elif event == 'motion':
        v.motion_detected = True
        v.last_motion_time = get_current_time()
        
    elif event == 'motion_check_timer':
        # Check if we've been in intertrial for at least intertrial_duration
        time_in_intertrial = get_current_time() - v.intertrial_start_time
        if time_in_intertrial >= v.intertrial_duration:
            if not v.motion_detected:
                # No motion detected for required duration, start appropriate trial type
                if v.current_block == 'contingent':
                    goto_state('trial_contingent')
                else:
                    goto_state('trial_random')
            else:
                # Motion was detected, reset timer and try again
                v.motion_detected = False
                set_timer('motion_check_timer', v.motion_wait_time, True)
        else:
            # Haven't reached minimum intertrial duration yet
            set_timer('motion_check_timer', v.motion_wait_time, True)
    
    elif event == 'stop_button':
        goto_state('stopped')

def trial_contingent(event):
    if event == 'entry':
        hw.speaker.sine(v.start_freq_hz)
        set_timer('trial_timer', v.trial_timeout_contingent, True)
        
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
    
    elif event == 'target_tone_timer':
        # Goal frequency playback finished, go to reward
        goto_state('reward')
    
    elif event == 'stop_button':
        goto_state('stopped')

def trial_random(event):
    if event == 'entry':
        # Select a random frequency from the possible frequencies
        v.random_freq_current = random.choice(v.random_frequencies)
        print('{}, random_frequency'.format(v.random_freq_current))
        hw.speaker.sine(v.random_freq_current)
        set_timer('random_tone_timer', v.trial_timeout_random, True)
        
    elif event == 'exit':
        disarm_timer('random_tone_timer')
        
    elif event == 'random_tone_timer':
        # Random tone duration finished
        goto_state('intertrial')
    
    elif event == 'stop_button':
        goto_state('stopped')

def reward(event):
    if event == 'entry':
        hw.speaker.off()
        set_timer('reward_timer', 5*second, True)  # 5 seconds to get reward
        
    elif event == 'exit':
        disarm_timer('reward_timer')
        
    elif event == 'lick':
        v.reward_number += 1
        if v.current_block == 'contingent':
            v.contingent_rewards += 1
        else:
            v.random_rewards += 1
        
        hw.reward.release()
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
        disarm_timer('random_tone_timer')
        disarm_timer('target_tone_timer')
        disarm_timer('block_timer')
    
    elif event == 'stop_button':
        goto_state('intertrial')

# -------------------------------------------------------------------------
# Event handlers
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'session_timer':
        print('Session Timer Expired')
        print('{}, total_rewards'.format(v.reward_number))
        print('{}, contingent_rewards'.format(v.contingent_rewards))
        print('{}, random_rewards'.format(v.random_rewards))
        stop_framework()
    
    elif event == 'block_timer':
        # Switch block type
        switch_block()
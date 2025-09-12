from pyControl.utility import *
import hardware_definition as hw
from devices import *

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
    'lick',
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
v.session_duration = 3 * minute

# Trial parameters
v.intertrial_duration = 4 * second
v.motion_wait_time = 1 * second     # Time without motion before trial can start
v.reward_duration = 40 * ms
v.target_present_duration = 1 * second  # Duration to play goal frequency
v.reward_trial_duration = 5 * second       # Max time to get reward

# Distance and frequency mapping
v.goal_freq_hz = 12000       # Goal frequency (Hz)

# Motion sensor parameters
v.cpi = 100                 # Counts per inch (will be updated from sensor)
v.motion_threshold = 10     # Motion event threshold

# Trial tracking
v.reward_number = 0
v.motion_detected = False   # Flag for motion during wait period
v.intertrial_start_time = 0 # Track when intertrial started

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
    print('{}, goal_frequency'.format(v.goal_freq_hz))
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
        v.motion_detected = False
        v.intertrial_start_time = get_current_time()
        # Start checking for motion after minimum intertrial duration
        set_timer('motion_check_timer', v.intertrial_duration, True)
        
    elif event == 'motion':
        v.motion_detected = True
        
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
        hw.speaker.sine(v.goal_freq_hz)
        set_timer('target_tone_timer', v.target_present_duration, True)
    
    elif event == 'target_tone_timer':
        # Goal frequency playback finished, go to reward
        goto_state('reward')
    
    elif event == 'stop_button':
        goto_state('stopped')

def reward(event):
    if event == 'entry':

        set_timer('reward_timer', v.reward_trial_duration, True)  # 5 seconds to get reward

    elif event == 'exit':
        disarm_timer('reward_timer')
        
    elif event == 'lick':
        v.reward_number += 1
        hw.reward.release()
        hw.speaker.off()
        print('{}, reward_number'.format(v.reward_number))
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
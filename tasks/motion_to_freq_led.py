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
    'lick',
    'trial_begin',
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
v.session_duration = 45 * minute

# Trial parameters
v.intertrial_duration = 2 * second
v.trial_timeout = 15 * second       # Max time to reach target distance
v.motion_wait_time = 0.5 * second     # Time without motion before trial can start
v.reward_duration = 35 * ms
v.target_present_duration = 1 * second  # Duration to play goal frequency
v.no_motion_before_reward = 0.5 * second  # Time without motion before reward can be triggered

# Distance and frequency mapping
v.goal_distance = 6       # Distance units to reach goal
v.current_distance = 0     # Accumulated distance traveled
v.start_freq_hz = 2000     # Starting frequency (Hz)
v.goal_freq_hz = 10000     # Goal frequency (Hz)

# Discrete frequency steps (speaker)
v.num_steps = 3            # Number of discrete frequency steps (like semitones)
v.current_step = 0         # Current frequency step
v.current_freq = v.start_freq_hz

# Motion sensor parameters
v.cpi = 100                # Counts per inch (will be updated from sensor)
v.motion_threshold = 2    # Motion event threshold

# Trial tracking
v.reward_number = 0
v.last_motion_time = 0     # Track when last motion occurred
v.motion_detected = False  # Flag for motion during wait period
v.intertrial_start_time = 0

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------
def calculate_frequency_for_step(step):
    """Calculate frequency for a given step using log scale (octaves)"""
    octaves = math.log2(v.goal_freq_hz / v.start_freq_hz)
    step_fraction = step / v.num_steps
    freq_multiplier = 2 ** (octaves * step_fraction)
    return int(v.start_freq_hz * freq_multiplier)

def led_percent_from_progress(progress: float) -> int:
    """Map progress [0..1] to LED strip percent for bilateral (side -> center).
    With bilateral mode, 0 ≈ side, 100 ≈ center. Clamp to [0..100]."""
    p = int(100 * max(0.0, min(1.0, progress)))
    return min(100, p)

def update_feedback_from_distance():
    """Update speaker and LED feedback based on current distance."""
    # Progress in [0,1]
    progress = min(v.current_distance / v.goal_distance, 1.0)

    # Speaker: discrete steps
    new_step = int(progress * v.num_steps)
    if new_step != v.current_step:
        v.current_step = new_step
        v.current_freq = calculate_frequency_for_step(v.current_step)
        hw.speaker.sine(v.current_freq)
        print('{}, distance'.format(v.current_distance))
        print('{}, frequency'.format(v.current_freq))

    # LED strip: bilateral side -> center
    try:
        led_p = led_percent_from_progress(progress)
        hw.light.cue(led_p)
        print('{}, led_percent'.format(led_p))
    except Exception as e:
        # If LED strip is unavailable, continue with audio only
        pass

    # Check if we've reached the goal (complete distance)
    if v.current_distance >= v.goal_distance:
        hw.speaker.sine(v.goal_freq_hz)
        print('{}, target_reached'.format(v.goal_freq_hz))
        set_timer('target_tone_timer', v.target_present_duration, True)

def reset_trial():
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

    # LED strip feedback (bilateral symmetric cue)
    try:
        hw.light.start()
        hw.light.all_red()
        hw.light.cue_bilateral(True)
        #hw.light.cue(50)  # start at sides
    except Exception:
        pass

    # Get actual CPI from sensor
    if hasattr(hw.motionSensor, 'sensor_x'):
        v.cpi = hw.motionSensor.sensor_x.CPI

    print('{}, CPI'.format(v.cpi))
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
    hw.speaker.off()
    try:
        hw.light.all_off()
        hw.light.off()
    except Exception:
        pass
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
        hw.light.all_red()
        reset_trial()
        v.motion_detected = False
        v.intertrial_start_time = get_current_time()
        set_timer('motion_check_timer', v.intertrial_duration, True)


    elif event == 'motion':
        v.motion_detected = True
        v.last_motion_time = get_current_time()

    elif event == 'motion_check_timer':
        time_in_intertrial = get_current_time() - v.intertrial_start_time
        if time_in_intertrial >= v.intertrial_duration:
            if not v.motion_detected:
                goto_state('trial')
            else:
                v.motion_detected = False
                set_timer('motion_check_timer', v.motion_wait_time, True)
        else:
            set_timer('motion_check_timer', v.motion_wait_time, True)

    elif event == 'stop_button':
        goto_state('stopped')

def trial(event):
    if event == 'entry':
        hw.light.cue(3)
        hw.speaker.sine(v.start_freq_hz)
        set_timer('trial_timer', v.trial_timeout, True)

    elif event == 'exit':
        disarm_timer('trial_timer')

    elif event == 'motion':
        # Accumulate distance on motion event
        v.current_distance += v.motion_threshold
        update_feedback_from_distance()
        v.last_motion_time = get_current_time()

    elif event == 'trial_timer':
        goto_state('intertrial')

    elif event == 'target_tone_timer':
        goto_state('reward')

    elif event == 'stop_button':
        goto_state('stopped')

def reward(event):
    if event == 'entry':
        set_timer('reward_timer', 5 * second, True)

    elif event == 'exit':
        disarm_timer('reward_timer')

    elif event == 'lick':
        if get_current_time() - v.last_motion_time > v.no_motion_before_reward:
            v.reward_number += 1
            hw.reward.release()
            hw.speaker.off()
            print('{}, reward_number'.format(v.reward_number))
            set_timer('trial_begin', v.intertrial_duration, True)
            goto_state('intertrial')
            
    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'reward_timer':
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
        try:
            hw.light.all_off()
        except Exception:
            pass

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


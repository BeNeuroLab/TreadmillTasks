from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math
import random

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'spontaneous_pre',
    'setup',
    'intertrial',
    'trial',
    'reward',
    'post_reward', # New state for stimulus hold after reward
    'stopped',
    'setup_post',
    'spontaneous_post'
]

events = [
    'session_timer',
    'state_timer',   # Consolidated timer event for state durations
    'motion',        # Motion events from sensor
    'lick',
    'stop_button'
]

initial_state = 'spontaneous_pre'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session parameters
v.session_duration = 45 * minute
v.spontaneous_duration = 5 * minute

# Manual triggers
v.start_task_now = False
v.start_spontaneous_post_now = False

# Trial parameters
v.intertrial_duration = 2 * second
v.trial_timeout = 15 * second       # Max time to reach target distance
v.motion_wait_time = 0.5 * second     # Time without motion before trial can start
v.reward_duration = 35 * ms
v.target_present_duration = 1 * second  # Duration to play goal frequency
v.no_motion_before_reward = 0.5 * second  # Time without motion before reward can be triggered

# Distance and frequency mapping
v.goal_distance_base = 60       # Base distance units to reach goal
v.goal_distance_jitter = 0.20   # ±20% randomization per trial
v.goal_distance = v.goal_distance_base
v.current_distance = 0          # Accumulated distance traveled
v.start_freq_hz = 2000          # Starting frequency (Hz)
v.goal_freq_hz = 10000          # Goal frequency (Hz)

# Discrete frequency steps (speaker)
v.num_steps = 10                # Number of discrete frequency steps (like semitones)
v.current_step = 0              # Current frequency step
v.current_freq = v.start_freq_hz

# Teleportation (jump) parameters
v.teleport_prob = 0.2           # 20% of trials are teleport trials
v.is_teleport_trial = False
v.teleport_trigger_index = 0    # Which step triggers the teleport
v.update_calls_in_trial = 0     # Count of step changes in current trial
v.trial_type_sequence = []      # List to manage block randomization

# Motion sensor parameters
v.cpi = 100                     # Counts per inch (will be updated from sensor)
v.motion_threshold = 3          # Motion event threshold

# Trial tracking
v.reward_number = 0
v.last_motion_time = 0          # Track when last motion occurred
v.motion_detected = False       # Flag for motion during wait period
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
    # Teleportation check: jump to goal on specific step
    if v.is_teleport_trial and (v.update_calls_in_trial == v.teleport_trigger_index):
        v.current_distance = v.goal_distance
        print('Teleporting to goal!')

    # Progress in [0,1]
    progress = min(v.current_distance / v.goal_distance, 1.0)

    # Speaker and LED: discrete steps (synchronized)
    new_step = int(progress * v.num_steps)
    if new_step != v.current_step:
        v.current_step = new_step
        v.update_calls_in_trial += 1
        v.current_freq = calculate_frequency_for_step(v.current_step)
        hw.speaker.sine(v.current_freq)
        print('{}, distance'.format(v.current_distance))
        print('{}, frequency'.format(v.current_freq))

        # LED strip: bilateral side -> center (update only on step change)
        try:
            led_p = led_percent_from_progress(progress)
            hw.light.cue(led_p)
            print('{}, led_percent'.format(led_p))
        except Exception:
            pass

    # Check if we've reached the goal (complete distance)
    # If goal reached, transition to reward info immediately
    if v.current_distance >= v.goal_distance:
        print('{}, target_reached'.format(v.goal_freq_hz))
        goto_state('reward')

def reset_trial():
    """Reset distance/frequency and apply random jitter to goal distance."""
    v.current_distance = 0
    v.current_step = 0
    v.current_freq = v.start_freq_hz
    v.motion_detected = False
    v.update_calls_in_trial = 0

    # Apply ±jitter% (uniform)
    jitter_fraction = 1 + random.uniform(-v.goal_distance_jitter, v.goal_distance_jitter)
    v.goal_distance = v.goal_distance_base * jitter_fraction
    print('{}, new_goal_distance'.format(round(v.goal_distance, 2)))

    # Determine trial type (Teleport vs Normal) using block randomization
    if not v.trial_type_sequence:
        # Refill sequence if empty
        block_size = 10
        num_teleports = int(block_size * v.teleport_prob)
        new_block = [True] * num_teleports + [False] * (block_size - num_teleports)
        # Shuffle the block
        for i in range(len(new_block) - 1, 0, -1):
            j = random.randint(0, i)
            new_block[i], new_block[j] = new_block[j], new_block[i]
        v.trial_type_sequence = new_block
        print('New trial block generated: {}'.format(v.trial_type_sequence))

    v.is_teleport_trial = v.trial_type_sequence.pop(0)

    if v.is_teleport_trial:
        v.teleport_trigger_index = random.choice([1, 2])
        print('Teleport Trial! Trigger on update #{}'.format(v.teleport_trigger_index))
    else:
        print('Normal Trial')

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
    print('{}, base_goal_distance'.format(v.goal_distance_base))
    print('{}, goal_jitter_fraction'.format(v.goal_distance_jitter))
    print('{}, num_steps'.format(v.num_steps))
    print('{}, teleport_prob'.format(v.teleport_prob))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()
    
    # Session timer NOT started here - starts after setup

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
# Spontaneous & Setup States
# -------------------------------------------------------------------------
def spontaneous_pre(event):
    if event == 'entry':
        print('Entering Spontaneous Pre-Task State ({}s)'.format(v.spontaneous_duration/second))
        set_timer('state_timer', v.spontaneous_duration)
    elif event == 'state_timer':
        goto_state('setup')
    elif event == 'motion':
        # Log motion but do nothing else
        v.last_motion_time = get_current_time()

def setup(event):
    if event == 'entry':
        print('In Setup State. Waiting for manual transition.')
        print('To start task: Change v.start_task_now to True in Variables tab.')
        set_timer('state_timer', 1 * second, True)
    elif event == 'state_timer':
        if v.start_task_now:
            goto_state('intertrial')
        else:
            set_timer('state_timer', 1 * second)
    elif event == 'exit':
        v.start_task_now = False # Reset for safety
        # This is where the actual task session starts counting
        set_timer('session_timer', v.session_duration)
        print('Setup Complete. Session Timer Started for {}s'.format(v.session_duration/second))
    elif event == 'motion':
        v.last_motion_time = get_current_time()

def setup_post(event):
    if event == 'entry':
        print('In Post-Task Setup State. Waiting for manual transition.')
        print('To start spontaneous post-task: Change v.start_spontaneous_post_now to True.')
        set_timer('state_timer', 1 * second, True)
    elif event == 'state_timer':
        if v.start_spontaneous_post_now:
            goto_state('spontaneous_post')
        else:
            set_timer('state_timer', 1 * second)
    elif event == 'exit':
        v.start_spontaneous_post_now = False
    elif event == 'motion':
        v.last_motion_time = get_current_time()

def spontaneous_post(event):
    if event == 'entry':
        print('Entering Spontaneous Post-Task State ({}s)'.format(v.spontaneous_duration/second))
        set_timer('state_timer', v.spontaneous_duration)
        hw.speaker.off()
        try:
            hw.light.all_off()
        except Exception:
            pass
        # Keep recording motion, but no stimuli
    elif event == 'state_timer':
        stop_framework()
    elif event == 'motion':
        v.last_motion_time = get_current_time()

# -------------------------------------------------------------------------
# State Machine
# -------------------------------------------------------------------------
# -------------------------------------------------------------------------
# State Machine
# -------------------------------------------------------------------------
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        try:
            hw.light.all_red()
        except:
            pass
        reset_trial()
        v.motion_detected = False
        v.intertrial_start_time = get_current_time()
        # Use state_timer for motion check
        set_timer('state_timer', v.intertrial_duration, True)

    elif event == 'motion':
        v.motion_detected = True
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        # Replaces motion_check_timer logic
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

def trial(event):
    if event == 'entry':
        try:
            hw.light.cue(3)
        except:
            pass
        hw.speaker.sine(v.start_freq_hz)
        # Use state_timer for trial timeout
        set_timer('state_timer', v.trial_timeout, True)

    elif event == 'exit':
        disarm_timer('state_timer')

    elif event == 'motion':
        # Accumulate distance on motion event
        v.current_distance += v.motion_threshold
        update_feedback_from_distance()
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        # Timeout reached
        goto_state('intertrial')

    elif event == 'stop_button':
        goto_state('stopped')

def reward(event):
    """
    Goal reached. Stimulus is ON.
    Wait for lick. If lick, give reward and move to post_reward (keep stim on).
    """
    if event == 'entry':
        # Start goal freq if not already (redundant but safe)
        hw.speaker.sine(v.goal_freq_hz)
        # Use state_timer for reward availability window
        set_timer('state_timer', 5 * second, True)

    elif event == 'exit':
        disarm_timer('state_timer')

    elif event == 'lick':
        if get_current_time() - v.last_motion_time > v.no_motion_before_reward:
            v.reward_number += 1
            hw.reward.release()
            print('{}, reward_number'.format(v.reward_number))
            # Move to post_reward to keep stimulus on for a bit
            goto_state('post_reward')

    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        # Reward window expired without valid lick
        goto_state('intertrial')

    elif event == 'stop_button':
        goto_state('stopped')

def post_reward(event):
    """
    Keep stimulus on for v.target_present_duration AFTER the reward.
    """
    if event == 'entry':
        set_timer('state_timer', v.target_present_duration, True)

    elif event == 'state_timer':
        goto_state('intertrial')
        
    elif event == 'stop_button':
        goto_state('stopped')

def stopped(event):
    if event == 'entry':
        hw.speaker.off()
        # Disarm consolidated timer
        disarm_timer('state_timer')
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
        # Move to post-task setup
        print('Session Timer Expired - Moving to Post-Task Setup')
        print('{}, total_rewards'.format(v.reward_number))
        goto_state('setup_post')

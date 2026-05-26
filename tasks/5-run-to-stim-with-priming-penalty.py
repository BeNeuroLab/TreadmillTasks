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
    'trial',
    'reward',          # Goal reached; wait for stillness to enter priming
    'priming',         # LED blinks; lick here to obtain reward
    'penalty',         # White noise + lights off after miss
    'post_reward',     # Keep stimulus after reward
    'stopped'
]

events = [
    'session_timer',
    'state_timer',     # General timer for state checks/windows
    'blink_timer',     # LED blink timer in priming
    'motion',          # Motion events from sensor
    'lick',
    'stop_button'
]

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session parameters
v.session_duration = 45 * minute

# Manual triggers (none)

# Trial parameters
v.intertrial_duration = 2 * second
v.trial_timeout = 15 * second         # Max time to reach target distance
v.motion_wait_time = 0.5 * second     # Time without motion before trial can start
v.reward_duration = 35 * ms
v.target_present_duration = 1 * second  # Duration to play goal frequency after reward

# Stop/priming parameters
v.priming_wait_time = 0.5 * second      # Required stillness before entering priming
v.priming_window = 3.0 * second         # Time in priming to obtain reward by lick
v.priming_blink_period = 250 * ms       # LED blink period during priming
v.stop_to_prime_timeout = 5.0 * second  # If staying in reward without stopping -> penalty

# Penalty parameters
v.penalty_duration = 1.0 * second
v.penalty_noise_max_freq = 10000        # Upper freq for white noise

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
v.teleport_idxs = [3, 5, 7]     # Step-change indices that can trigger teleport
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
v.reward_entry_time = 0         # Track time of entering reward state

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
    """Map progress [0..1] to LED strip percent for bilateral (side -> center)."""
    p = int(100 * max(0.0, min(1.0, progress)))
    return min(100, p)

def set_led_blinking(enabled: bool):
    try:
        if enabled:
            # Background stays red; blink will toggle the target LED blue/red
            hw.light.all_red()
            v._blink_on = False
            set_timer('blink_timer', v.priming_blink_period, True)
        else:
            disarm_timer('blink_timer')
            try:
                hw.light.all_red()
            except Exception:
                pass
    except Exception:
        pass

def toggle_led():
    """Blink by alternating the target LED between blue (cue) and red background only."""
    try:
        if getattr(v, '_blink_on', False):
            # Turn target back to red background only
            hw.light.all_red()
            v._blink_on = False
        else:
            # Show target LED in blue while others remain red
            hw.light.cue(v.target_led_percent)
            v._blink_on = True
    except Exception:
        pass

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
        block_size = 10
        num_teleports = int(block_size * v.teleport_prob)
        new_block = [True] * num_teleports + [False] * (block_size - num_teleports)
        for i in range(len(new_block) - 1, 0, -1):
            j = random.randint(0, i)
            new_block[i], new_block[j] = new_block[j], new_block[i]
        v.trial_type_sequence = new_block
        print('New trial block generated: {}'.format(v.trial_type_sequence))

    v.is_teleport_trial = v.trial_type_sequence.pop(0)
    if v.is_teleport_trial:
        v.teleport_trigger_index = random.choice(v.teleport_idxs)
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

    try:
        hw.light.start()
        hw.light.all_red()
        hw.light.cue_bilateral(True)
    except Exception:
        pass

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
    print('{}, teleport_idxs'.format(v.teleport_idxs))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()
    # Start the session timer immediately since there is no setup state.
    set_timer('session_timer', v.session_duration)

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
# No setup/spontaneous states in this task
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
        set_timer('state_timer', v.intertrial_duration, True)

    elif event == 'motion':
        v.motion_detected = True
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
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
    
    elif event == 'exit':
        # Ensure no intertrial timers bleed into next state
        disarm_timer('state_timer')

def trial(event):
    if event == 'entry':
        # Defensive: clear any lingering state_timer from previous state
        disarm_timer('state_timer')
        try:
            hw.light.cue(3)
        except:
            pass
        hw.speaker.sine(v.start_freq_hz)
        set_timer('state_timer', v.trial_timeout, True)

    elif event == 'exit':
        disarm_timer('state_timer')

    elif event == 'motion':
        v.current_distance += v.motion_threshold
        update_feedback_from_distance()
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        # Trial timeout without reaching target -> penalty first
        goto_state('penalty')

    elif event == 'stop_button':
        goto_state('stopped')

def reward(event):
    """
    Goal reached. Keep goal tone. Require sustained stillness to enter priming.
    If not still within stop_to_prime_timeout -> penalty.
    """
    if event == 'entry':
        hw.speaker.sine(v.goal_freq_hz)
        v.reward_entry_time = get_current_time()
        set_timer('state_timer', 50 * ms, True)  # periodic check

    elif event == 'exit':
        disarm_timer('state_timer')

    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        now = get_current_time()
        # Check for transition to priming after sufficient stillness
        if now - v.last_motion_time >= v.priming_wait_time:
            goto_state('priming')
        elif now - v.reward_entry_time >= v.stop_to_prime_timeout:
            goto_state('penalty')
        else:
            # Keep checking periodically until either condition is met
            set_timer('state_timer', 50 * ms)

    elif event == 'stop_button':
        goto_state('stopped')

def priming(event):
    """
    LED blinks to signal priming. Lick within priming_window to obtain reward.
    """
    if event == 'entry':
        # Keep goal tone, start LED blinking and window timer
        hw.speaker.sine(v.goal_freq_hz)
        # Target LED index (center when using bilateral mapping)
        v.target_led_percent = 100
        set_led_blinking(True)
        set_timer('state_timer', v.priming_window)

    elif event == 'exit':
        set_led_blinking(False)
        disarm_timer('blink_timer')
        disarm_timer('state_timer')

    elif event == 'blink_timer':
        toggle_led()
        # Reschedule next blink while in priming
        set_timer('blink_timer', v.priming_blink_period)

    elif event == 'lick':
        # Reward available during priming
        v.reward_number += 1
        hw.reward.release()
        print('{}, reward_number'.format(v.reward_number))
        goto_state('post_reward')

    elif event == 'state_timer':
        # Missed lick during priming
        goto_state('penalty')

    elif event == 'stop_button':
        goto_state('stopped')

def penalty(event):
    """
    Lights off and white noise for penalty_duration, then return to intertrial.
    Triggered by: no stop before priming window or no lick during priming.
    """
    if event == 'entry':
        try:
            hw.light.all_off()
        except Exception:
            pass
        hw.speaker.noise(v.penalty_noise_max_freq)
        set_timer('state_timer', v.penalty_duration)

    elif event == 'state_timer':
        goto_state('intertrial')

    elif event == 'exit':
        hw.speaker.off()
        disarm_timer('state_timer')

    elif event == 'stop_button':
        goto_state('stopped')

def post_reward(event):
    """
    Keep goal stimulus on for v.target_present_duration AFTER the reward.
    """
    if event == 'entry':
        # Ensure steady goal sound and target LED (no blinking)
        hw.speaker.sine(v.goal_freq_hz)
        try:
            if not hasattr(v, 'target_led_percent'):
                v.target_led_percent = 100
            hw.light.all_red()
            hw.light.cue(v.target_led_percent)
        except Exception:
            pass
        set_timer('state_timer', v.target_present_duration)

    elif event == 'state_timer':
        goto_state('intertrial')

    elif event == 'stop_button':
        goto_state('stopped')
    
    elif event == 'exit':
        disarm_timer('state_timer')

def stopped(event):
    if event == 'entry':
        hw.speaker.off()
        disarm_timer('state_timer')
        disarm_timer('blink_timer')
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
        print('Session Timer Expired - Stopping Framework')
        print('{}, total_rewards'.format(v.reward_number))
        stop_framework()

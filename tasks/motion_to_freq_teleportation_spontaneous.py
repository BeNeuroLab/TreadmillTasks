# ===== Task with dynamic stillness-before-reward and goal-distance jitter + Spontaneous States =====
from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math, random

# -------------------------------------------------------------------------
# States / Events
# -------------------------------------------------------------------------
states = ['spontaneous_pre', 'setup', 'intertrial', 'trial', 'reward', 'spontaneous_post']
events = ['lick', 'motion', 'session_timer', 'quiescence_timer', 'spontaneous_timer']
initial_state = 'spontaneous_pre'

# -------------------------------------------------------------------------
# Session / trial params
# -------------------------------------------------------------------------
v.session_duration       = 45 * minute
v.spontaneous_duration   = 5 * minute  # Standard duration for pre/post

v.intertrial_duration    = 3 * second
v.motion_wait_time       = 1 * second
v.first_trial_extra_wait = 3 * second

v.trial_timeout          = 15 * second
v.reward_window          = 3 * second
v.reward_duration        = 40 * ms
v.target_present_duration= 1 * second

v.no_motion_before_reward = 0.5 * second   # must stay still this long before reward


# Teleportation params
v.teleport_prob = 0.2  # 10% of trials
v.is_teleport_trial = False
v.teleport_trigger_index = 0
v.update_calls_in_trial = 0
v.trial_type_sequence = [] # List to manage block randomization

# Distance/frequency mapping

v.current_distance= 0
v.start_freq_hz   = 2000
v.goal_freq_hz    = 10000
v.num_steps       = 5
v.current_step    = 0
v.current_freq    = v.start_freq_hz

# Motion sensor
v.cpi               = 100
v.motion_threshold  = 3

v.goal_distance_base      = v.motion_threshold *  v.num_steps             # base distance units
v.goal_distance_jitter    = 0.20            # ±25% randomisation per trial
v.goal_distance   = v.goal_distance_base

# Tracking
v.reward_number     = 0
v.last_motion_time  = 0
v.intertrial_entry_time = 0
v.first_trial       = 1

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def calculate_frequency_for_step(step):
    """Log/octave spacing between start and goal, discretised into num_steps."""
    octaves = math.log2(v.goal_freq_hz / v.start_freq_hz)
    step_fraction = step / v.num_steps
    return int(v.start_freq_hz * (2 ** (octaves * step_fraction)))

def update_frequency_from_distance():
    """Update frequency only on step changes; go to reward when goal reached."""
    
    
    # Teleportation check
    if v.is_teleport_trial and (v.update_calls_in_trial == v.teleport_trigger_index):
        v.current_distance = v.goal_distance
        print('Teleporting to goal!')

    progress = min(v.current_distance / v.goal_distance, 1.0)
    new_step = int(progress * v.num_steps)
    if new_step != v.current_step:
        v.current_step = new_step
        v.update_calls_in_trial += 1
        v.current_freq = calculate_frequency_for_step(v.current_step)
        hw.speaker.sine(v.current_freq)
        print('{}, distance'.format(v.current_distance))
        print('{}, frequency'.format(v.current_freq))

    if v.current_distance >= v.goal_distance:
        hw.speaker.sine(v.goal_freq_hz)
        print('{}, target_reached'.format(v.goal_freq_hz))
        timed_goto_state('reward', v.target_present_duration)

def reset_trial_vars():
    """Reset distance/frequency and apply random jitter to goal distance."""
    v.current_distance = 0
    v.current_step     = 0
    v.current_freq     = v.start_freq_hz
    # Apply ±25% jitter (uniform)
    jitter_fraction = 1 + random.uniform(-v.goal_distance_jitter, v.goal_distance_jitter)
    v.goal_distance = v.goal_distance_base * jitter_fraction
    print('{}, new_goal_distance'.format(round(v.goal_distance, 2)))

    # Determine trial type (Teleport vs Normal) using block randomization
    if not v.trial_type_sequence:
        # Refill sequence if empty
        # e.g. if prob is 0.1, we want 1 True and 9 False (assuming 10 trial block)
        # We'll use a fixed block size of 10 for simplicity to guarantee "1 in 10" exactly.
        block_size = 10
        num_teleports = int(block_size * v.teleport_prob)
        # Ensure at least one teleport if prob > 0 but < 1/block_size? 
        # For now, strictly follow the math: 0.1 * 10 = 1.
        new_block = [True] * num_teleports + [False] * (block_size - num_teleports)
        for i in range(len(new_block) - 1, 0, -1):
            j = random.randint(0, i)
            new_block[i], new_block[j] = new_block[j], new_block[i]
        v.trial_type_sequence = new_block
        print('New trial block generated: {}'.format(v.trial_type_sequence))

    v.is_teleport_trial = v.trial_type_sequence.pop(0)
    v.update_calls_in_trial = 0
    
    if v.is_teleport_trial:
        v.teleport_trigger_index = random.choice([1, 2])
        print('Teleport Trial! Trigger on update #{}'.format(v.teleport_trigger_index))
    else:
        print('Normal Trial')


def arm_quiescence_check():
    """Rearming timer to gate intertrial exit based on both time and stillness."""
    now = get_current_time()
    min_ITI = v.first_trial_extra_wait if v.first_trial else v.intertrial_duration
    since_entry = now - v.intertrial_entry_time
    since_motion = now - v.last_motion_time

    need_ITI_ms   = max(0, min_ITI - since_entry)
    need_quiet_ms = max(0, v.motion_wait_time - since_motion)

    if (need_ITI_ms == 0) and (need_quiet_ms == 0):
        goto_state('trial')
    else:
        delay = max(need_ITI_ms, need_quiet_ms, 50)
        set_timer('quiescence_timer', delay, True)

# -------------------------------------------------------------------------
# Run start/end
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(15)
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_threshold
    hw.reward.reward_duration = v.reward_duration
    hw.light.start()
    hw.light.off()

    if hasattr(hw.motionSensor, 'sensor_x'):
        v.cpi = hw.motionSensor.sensor_x.CPI

    print('{}, motion_threshold'.format(v.motion_threshold))
    print('{}, trial_timeout'.format(v.trial_timeout))
    print('{}, start_frequency'.format(v.start_freq_hz))
    print('{}, goal_frequency'.format(v.goal_freq_hz))
    print('{}, base_goal_distance'.format(v.goal_distance_base))
    print('{}, goal_jitter_fraction'.format(v.goal_distance_jitter))
    print('{}, num_steps'.format(v.num_steps))
    print('{}, teleport_prob'.format(v.teleport_prob))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

    # NOTE: Session timer is NOT started here anymore. It starts in 'setup' exit.
    
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
# Spontaneous & Setup States
# -------------------------------------------------------------------------

def spontaneous_pre(event):
    if event == 'entry':
        print('Entering Spontaneous Pre-Task State ({}s)'.format(v.spontaneous_duration/second))
        set_timer('spontaneous_timer', v.spontaneous_duration)
    elif event == 'spontaneous_timer':
        goto_state('setup')
    elif event == 'motion':
        # Log motion but do nothing else
        v.last_motion_time = get_current_time()

def setup(event):
    if event == 'entry':
        print('In Setup State. Waiting for manual transition.')
        print('Human: Please switch to "intertrial" or "trial" state manually to begin task.')
    elif event == 'exit':
        # This is where the actual task session starts counting
        set_timer('session_timer', v.session_duration)
        print('Setup Complete. Session Timer Started for {}s'.format(v.session_duration/second))
    elif event == 'motion':
        v.last_motion_time = get_current_time()

def spontaneous_post(event):
    if event == 'entry':
        print('Entering Spontaneous Post-Task State ({}s)'.format(v.spontaneous_duration/second))
        set_timer('spontaneous_timer', v.spontaneous_duration)
        hw.speaker.off()
        hw.light.off() 
        # Keep recording motion, but no stimuli
    elif event == 'spontaneous_timer':
        stop_framework()
    elif event == 'motion':
        v.last_motion_time = get_current_time()

# -------------------------------------------------------------------------
# Task States
# -------------------------------------------------------------------------
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        reset_trial_vars()
        v.last_motion_time = get_current_time()
        v.intertrial_entry_time = v.last_motion_time
        arm_quiescence_check()

    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'quiescence_timer':
        arm_quiescence_check()

    elif event == 'exit':
        disarm_timer('quiescence_timer')
        v.first_trial = 0

def trial(event):
    if event == 'entry':
        hw.speaker.sine(v.start_freq_hz)
        timed_goto_state('intertrial', v.trial_timeout)

    elif event == 'motion':
        v.current_distance += v.motion_threshold
        update_frequency_from_distance()
        v.last_motion_time = get_current_time()

    elif event == 'exit':
        hw.speaker.off()

def reward(event):
    """
    The animal has v.reward_window to lick for reward,
    but must first remain still for v.no_motion_before_reward seconds.
    """
    if event == 'entry':
        print('Entered reward state, stillness required before reward.')
        # v.last_motion_time = get_current_time()
        timed_goto_state('intertrial', v.reward_window)
        # set_timer('target_timer', v.target_present_duration, True)

    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'lick':
        time_since_motion = get_current_time() - v.last_motion_time
        if time_since_motion >= v.no_motion_before_reward:
            v.reward_number += 1
            hw.reward.release()
            hw.speaker.off()
            print('{}, reward_number'.format(v.reward_number))
            # disarm_timer('target_timer')
            goto_state('intertrial')

    # elif event == 'target_timer':
    #     hw.speaker.off()

    elif event == 'exit':
        hw.speaker.off()
        # disarm_timer('target_timer')

# -------------------------------------------------------------------------
# Global handler
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'session_timer':
        print('Session Timer Expired - Moving to Spontaneous Post')
        print('{}, total_rewards'.format(v.reward_number))
        # Move to post-spontaneous instead of stopping immediately
        goto_state('spontaneous_post')

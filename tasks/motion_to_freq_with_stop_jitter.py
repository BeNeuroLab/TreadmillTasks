# ===== Task with dynamic stillness-before-reward and goal-distance jitter =====
from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math, random

# -------------------------------------------------------------------------
# States / Events
# -------------------------------------------------------------------------
states = ['intertrial', 'trial', 'reward']
events = ['lick', 'motion', 'session_timer', 'quiescence_timer']
initial_state = 'trial'

# -------------------------------------------------------------------------
# Session / trial params
# -------------------------------------------------------------------------
v.session_duration       = 45 * minute

v.intertrial_duration    = 3 * second
v.motion_wait_time       = 1 * second
v.first_trial_extra_wait = 3 * second

v.trial_timeout          = 15 * second
v.reward_window          = 3 * second
v.reward_duration        = 40 * ms
v.target_present_duration= 1 * second

v.no_motion_before_reward = 1.5 * second   # must stay still this long before reward
v.goal_distance_base      = 10              # base distance units
v.goal_distance_jitter    = 0.25            # ±25% randomisation per trial

# Distance/frequency mapping
v.goal_distance   = v.goal_distance_base
v.current_distance= 0
v.start_freq_hz   = 2000
v.goal_freq_hz    = 10000
v.num_steps       = 5
v.current_step    = 0
v.current_freq    = v.start_freq_hz

# Motion sensor
v.cpi               = 100
v.motion_threshold  = 2

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
    progress = min(v.current_distance / v.goal_distance, 1.0)
    new_step = int(progress * v.num_steps)
    if new_step != v.current_step:
        v.current_step = new_step
        v.current_freq = calculate_frequency_for_step(v.current_step)
        hw.speaker.sine(v.current_freq)
        print('{}, distance'.format(v.current_distance))
        print('{}, frequency'.format(v.current_freq))

    if v.current_distance >= v.goal_distance:
        hw.speaker.sine(v.goal_freq_hz)
        print('{}, target_reached'.format(v.goal_freq_hz))
        timed_goto_state('reward', v.reward_window)

def reset_trial_vars():
    """Reset distance/frequency and apply random jitter to goal distance."""
    v.current_distance = 0
    v.current_step     = 0
    v.current_freq     = v.start_freq_hz
    # Apply ±25% jitter (uniform)
    jitter_fraction = 1 + random.uniform(-v.goal_distance_jitter, v.goal_distance_jitter)
    v.goal_distance = v.goal_distance_base * jitter_fraction
    print('{}, new_goal_distance'.format(round(v.goal_distance, 2)))

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
# States
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

    elif event == 'exit':
        hw.speaker.off()

def reward(event):
    """
    The animal has v.reward_window to lick for reward,
    but must first remain still for v.no_motion_before_reward seconds.
    """
    if event == 'entry':
        print('Entered reward state, stillness required before reward.')
        v.last_motion_time = get_current_time()
        timed_goto_state('intertrial', v.reward_window)

    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'lick':
        time_since_motion = get_current_time() - v.last_motion_time
        if time_since_motion >= v.no_motion_before_reward:
            v.reward_number += 1
            hw.reward.release()
            hw.speaker.off()
            print('{}, reward_number'.format(v.reward_number))
            goto_state('intertrial')

    elif event == 'exit':
        hw.speaker.off()

# -------------------------------------------------------------------------
# Global handler
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'session_timer':
        print('Session Timer Expired')
        print('{}, total_rewards'.format(v.reward_number))
        stop_framework()

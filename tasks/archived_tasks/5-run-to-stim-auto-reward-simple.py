"""Run to target with throttled feedback, stop briefly, then auto reward."""

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math


# -------------------------------------------------------------------------
# States and events
# -------------------------------------------------------------------------
states = [
    'intertrial',
    'trial',
    'wait_for_stop',
    'reward',
    'stopped',
]

events = [
    'session_timer',
    'state_timer',
    'motion',
    'stop_button',
]

initial_state = 'intertrial'


# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
v.session_duration = 45 * minute
v.intertrial_duration = 2 * second
v.trial_timeout = 15 * second

v.reward_duration = 35 * ms
v.reward_wait_time = 0.5 * second
v.stop_to_reward_timeout = 5 * second
v.reward_post_delay = 0.5 * second

v.target_distance = 60
v.current_distance = 0
v.motion_threshold = 2

v.start_freq_hz = 2000
v.goal_freq_hz = 10000
v.feedback_steps = 5
v.feedback_min_interval = 250 * ms
v.start_led_percent = 3

v.reward_number = 0
v.cpi = 100
v.last_motion_time = 0
v.target_reached_time = 0
v.current_feedback_step = -1
v.last_feedback_update_time = 0


# -------------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------------
def calculate_frequency_for_step(step):
    """Map feedback step to tone frequency on a log scale."""
    step_fraction = step / v.feedback_steps
    octaves = math.log2(v.goal_freq_hz / v.start_freq_hz)
    return int(v.start_freq_hz * (2 ** (octaves * step_fraction)))


def led_percent_for_step(step):
    percent = int(100 * step / v.feedback_steps)
    return max(v.start_led_percent, min(100, percent))


def apply_feedback_step(step):
    v.current_feedback_step = step
    v.last_feedback_update_time = get_current_time()
    hw.speaker.sine(calculate_frequency_for_step(step))
    try:
        hw.light.cue(led_percent_for_step(step))
    except Exception:
        pass


def update_feedback_from_distance(force=False):
    progress = min(v.current_distance / v.target_distance, 1.0)
    next_step = int(progress * v.feedback_steps)
    now = get_current_time()

    if force:
        apply_feedback_step(v.feedback_steps)
    elif (
        next_step != v.current_feedback_step
        and now - v.last_feedback_update_time >= v.feedback_min_interval
    ):
        apply_feedback_step(next_step)


def reset_trial():
    v.current_distance = 0
    v.current_feedback_step = -1
    v.last_feedback_update_time = get_current_time() - v.feedback_min_interval


# -------------------------------------------------------------------------
# Run start/end
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
    print('{}, target_distance'.format(v.target_distance))
    print('{}, feedback_steps'.format(v.feedback_steps))
    print('{}, feedback_min_interval'.format(v.feedback_min_interval))
    print('{}, reward_wait_time'.format(v.reward_wait_time))
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
# State machine
# -------------------------------------------------------------------------
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        try:
            hw.light.all_red()
        except Exception:
            pass
        reset_trial()
        set_timer('state_timer', v.intertrial_duration)

    elif event == 'state_timer':
        goto_state('trial')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')


def trial(event):
    if event == 'entry':
        reset_trial()
        print('{}, trial_start'.format(get_current_time()))
        apply_feedback_step(0)
        set_timer('state_timer', v.trial_timeout)

    elif event == 'motion':
        v.current_distance += v.motion_threshold
        v.last_motion_time = get_current_time()

        if v.current_distance >= v.target_distance:
            update_feedback_from_distance(force=True)
            print('{}, target_reached'.format(get_current_time()))
            goto_state('wait_for_stop')
        else:
            update_feedback_from_distance()

    elif event == 'state_timer':
        print('{}, trial_timeout'.format(get_current_time()))
        goto_state('intertrial')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')


def wait_for_stop(event):
    if event == 'entry':
        v.target_reached_time = get_current_time()
        v.last_motion_time = get_current_time()
        set_timer('state_timer', 50 * ms)

    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        now = get_current_time()
        if now - v.last_motion_time >= v.reward_wait_time:
            goto_state('reward')
        elif now - v.target_reached_time >= v.stop_to_reward_timeout:
            print('{}, stop_timeout'.format(get_current_time()))
            goto_state('intertrial')
        else:
            set_timer('state_timer', 50 * ms)

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')


def reward(event):
    if event == 'entry':
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        timed_goto_state('intertrial', v.reward_post_delay)

    elif event == 'stop_button':
        goto_state('stopped')


def stopped(event):
    if event == 'entry':
        hw.speaker.off()
        disarm_timer('state_timer')
        try:
            hw.light.all_off()
        except Exception:
            pass

    elif event == 'stop_button':
        goto_state('intertrial')


def all_states(event):
    if event == 'session_timer':
        print('Session Timer Expired - Stopping Framework')
        print('{}, total_rewards'.format(v.reward_number))
        stop_framework()

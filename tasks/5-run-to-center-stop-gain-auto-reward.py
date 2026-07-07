"""Run side-to-center visual cue, stop at target, then auto reward."""

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math
import random


# -------------------------------------------------------------------------
# States and events
# -------------------------------------------------------------------------
states = [
    'intertrial',
    'trial',
    'target_wait',
    'reward',
    'failed_trial',
    'stopped',
]

events = [
    'session_timer',
    'state_timer',
    'tone_off_timer',
    'motion',
    'lick',
    'stop_button',
]

initial_state = 'intertrial'


# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session timing.
v.session_duration = 45 * minute
v.intertrial_duration = 2 * second
v.trial_timeout = 15 * second
v.failed_trial_timeout = 2 * second
v.reward_cue_hold = 0.5 * second

# Reward and stopping rule.
v.reward_duration = 30 * ms
v.reward_wait_time = 0.5 * second
v.stop_to_reward_timeout = 5 * second
v.stop_check_interval = 50 * ms

# Distance and visual gain.
v.goal_distance_base = 60
v.goal_distance_jitter = 0.0
v.goal_distance = v.goal_distance_base
v.current_distance = 0
v.visual_gain = 1.0
v.trial_condition = 'normal'

# Gain block counts.  Use 14/3/3 for recording 70/15/15 normal/low/high.
v.normal_gain = 1.0
v.low_gain = 0.5
v.high_gain = 1.5
v.normal_gain_count = 20
v.low_gain_count = 0
v.high_gain_count = 0
v.gain_trial_queue = []
v.gain_block_number = 0

# LED states.  The final parsed entry is always the steady center target.
v.led_positions_csv = '35,50,65,80,100'
v.led_positions = []
v.num_led_positions = 0
v.current_led_index = -1
v.current_led_percent = 0

# Brief logarithmic tone pips.
v.audio_mode = 'step_pips'
v.start_tone_freq_hz = 2000
v.target_tone_freq_hz = 10000
v.step_tone_duration = 100 * ms
v.target_tone_duration = 150 * ms
v.current_tone_freq_hz = 0

# Optional penalty, off by default for recording.
v.use_noise_penalty = False
v.penalty_noise_max_freq = 10000

# Motion sensor.
v.cpi = None
v.motion_threshold = 3
v.forward_sign = 1
v.moving_at_cue_window = 250 * ms

# Trial tracking.
v.reward_number = 0
v.failure_number = 0
v.lick_number = 0
v.trial_number = 0
v.last_motion_time = 0
v.intertrial_start_time = 0
v.trial_start_time = 0
v.target_reached_time = 0
v.iti_motion_distance = 0
v.moving_at_cue_on = False
v.failure_reason = ''


# -------------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------------
def clipped_progress(progress):
    return max(0.0, min(1.0, progress))


def parse_csv_ints(csv_text):
    values = []
    for item in csv_text.split(','):
        item = item.strip()
        if item:
            values.append(int(item))
    return values


def configure_led_positions():
    v.led_positions = parse_csv_ints(v.led_positions_csv)
    v.num_led_positions = len(v.led_positions)
    if v.num_led_positions < 2:
        raise Exception('led_positions_csv must contain at least 2 positions')


def shuffle_block(block):
    for i in range(len(block) - 1, 0, -1):
        j = random.randint(0, i)
        block[i], block[j] = block[j], block[i]
    return block


def build_gain_block():
    block = []

    for i in range(max(0, int(v.normal_gain_count))):
        block.append('normal')
    for i in range(max(0, int(v.low_gain_count))):
        block.append('low')
    for i in range(max(0, int(v.high_gain_count))):
        block.append('high')

    if not block:
        block.append('normal')

    return shuffle_block(block)


def configure_gain_trial():
    if not v.gain_trial_queue:
        v.gain_trial_queue = build_gain_block()
        v.gain_block_number += 1
        print('{}, new_gain_block block={} order={}'.format(
            get_current_time(),
            v.gain_block_number,
            v.gain_trial_queue,
        ))

    v.trial_condition = v.gain_trial_queue.pop(0)

    if v.trial_condition == 'low':
        v.visual_gain = v.low_gain
    elif v.trial_condition == 'high':
        v.visual_gain = v.high_gain
    else:
        v.trial_condition = 'normal'
        v.visual_gain = v.normal_gain


def configure_goal_distance():
    jitter_fraction = 1 + random.uniform(
        -v.goal_distance_jitter,
        v.goal_distance_jitter,
    )
    v.goal_distance = v.goal_distance_base * jitter_fraction


def forward_delta_distance():
    """Return positive x-axis motion since the last motion event in cm."""
    if v.cpi is None:
        raise Exception('Motion sensor CPI unavailable')

    forward_counts = v.forward_sign * hw.motionSensor.x
    if forward_counts < 0:
        forward_counts = 0

    return forward_counts / v.cpi * 2.54


def visual_progress():
    if v.goal_distance <= 0:
        return 1.0
    return v.current_distance * v.visual_gain / v.goal_distance


def led_index_from_progress(progress):
    if progress >= 1.0:
        return v.num_led_positions - 1
    return int(clipped_progress(progress) * (v.num_led_positions - 1))


def tone_frequency_for_index(index):
    if v.num_led_positions <= 1:
        return int(v.target_tone_freq_hz)

    fraction = index / (v.num_led_positions - 1)
    ratio = v.target_tone_freq_hz / v.start_tone_freq_hz
    return int(v.start_tone_freq_hz * (ratio ** fraction))


def set_led_baseline():
    try:
        hw.light.all_red()
    except Exception:
        pass


def set_led_state(index):
    v.current_led_index = index
    v.current_led_percent = v.led_positions[index]
    try:
        hw.light.cue(v.current_led_percent)
    except Exception:
        pass

    print('{}, led_update index={} percent={} visual_progress={}'.format(
        get_current_time(),
        v.current_led_index,
        v.current_led_percent,
        round(clipped_progress(visual_progress()), 3),
    ))


def play_tone_for_led(index):
    if v.audio_mode != 'step_pips':
        hw.speaker.off()
        return

    v.current_tone_freq_hz = tone_frequency_for_index(index)
    hw.speaker.sine(v.current_tone_freq_hz)

    if index == v.num_led_positions - 1:
        duration = v.target_tone_duration
    else:
        duration = v.step_tone_duration

    set_timer('tone_off_timer', duration)
    print('{}, tone_update index={} frequency={} duration={}'.format(
        get_current_time(),
        index,
        v.current_tone_freq_hz,
        duration,
    ))


def apply_led_state(index, force=False):
    if force or index != v.current_led_index:
        set_led_state(index)
        play_tone_for_led(index)


def ensure_led_state(index):
    if index != v.current_led_index:
        set_led_state(index)


def update_cues_from_progress(force=False):
    progress = visual_progress()
    next_index = led_index_from_progress(progress)
    apply_led_state(next_index, force)
    return progress >= 1.0


def target_led_index():
    return v.num_led_positions - 1


def reset_trial_variables():
    v.current_distance = 0
    v.current_led_index = -1
    v.current_led_percent = 0
    v.current_tone_freq_hz = 0
    v.target_reached_time = 0
    v.trial_start_time = 0
    v.failure_reason = ''
    configure_goal_distance()
    configure_gain_trial()


def enter_failed_trial(reason):
    v.failure_number += 1
    v.failure_reason = reason
    print('{}, trial_failure reason={} distance={} visual_progress={}'.format(
        get_current_time(),
        reason,
        round(v.current_distance, 2),
        round(clipped_progress(visual_progress()), 3),
    ))
    goto_state('failed_trial')


def stop_detected():
    return get_current_time() - v.last_motion_time >= v.reward_wait_time


def stop_wait_timed_out():
    return get_current_time() - v.target_reached_time >= v.stop_to_reward_timeout


def moving_at_cue_on():
    return get_current_time() - v.last_motion_time <= v.moving_at_cue_window


# -------------------------------------------------------------------------
# Run start/end
# -------------------------------------------------------------------------
def run_start():
    configure_led_positions()

    hw.speaker.set_volume(15)
    hw.speaker.off()
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_threshold
    hw.reward.reward_duration = v.reward_duration

    try:
        hw.light.start()
        hw.light.all_red()
        hw.light.cue_bilateral(True)
    except Exception:
        pass

    if hw.motionSensor.sensor_x is None:
        raise Exception('Motion sensor CPI unavailable; sensor_x not initialized')
    v.cpi = hw.motionSensor.sensor_x.CPI

    print('{}, CPI'.format(v.cpi))
    print('{}, motion_threshold'.format(v.motion_threshold))
    print('{}, forward_sign'.format(v.forward_sign))
    print('{}, session_duration'.format(v.session_duration))
    print('{}, intertrial_duration'.format(v.intertrial_duration))
    print('{}, trial_timeout'.format(v.trial_timeout))
    print('{}, reward_duration'.format(v.reward_duration))
    print('{}, reward_wait_time'.format(v.reward_wait_time))
    print('{}, stop_to_reward_timeout'.format(v.stop_to_reward_timeout))
    print('{}, goal_distance_base'.format(v.goal_distance_base))
    print('{}, goal_distance_jitter'.format(v.goal_distance_jitter))
    print('{}, led_positions_csv'.format(v.led_positions_csv))
    print('{}, num_led_positions'.format(v.num_led_positions))
    print('{}, start_tone_freq_hz'.format(v.start_tone_freq_hz))
    print('{}, target_tone_freq_hz'.format(v.target_tone_freq_hz))
    print('{}, step_tone_duration'.format(v.step_tone_duration))
    print('{}, target_tone_duration'.format(v.target_tone_duration))
    print('{}, normal_gain'.format(v.normal_gain))
    print('{}, low_gain'.format(v.low_gain))
    print('{}, high_gain'.format(v.high_gain))
    print('{}, normal_gain_count'.format(v.normal_gain_count))
    print('{}, low_gain_count'.format(v.low_gain_count))
    print('{}, high_gain_count'.format(v.high_gain_count))
    print('{}, use_noise_penalty'.format(v.use_noise_penalty))
    print('{}, before_camera_trigger'.format(get_current_time()))

    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration, True)


def run_end():
    hw.speaker.off()
    hw.reward.stop()
    try:
        hw.light.all_off()
        hw.light.off()
    except Exception:
        pass
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.off()
    print('{}, total_rewards'.format(v.reward_number))
    print('{}, total_failures'.format(v.failure_number))
    print('{}, total_licks'.format(v.lick_number))
    print('Session Ended')


# -------------------------------------------------------------------------
# State machine
# -------------------------------------------------------------------------
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        disarm_timer('tone_off_timer')
        set_led_baseline()
        reset_trial_variables()
        v.iti_motion_distance = 0
        v.intertrial_start_time = get_current_time()
        print('{}, iti_start'.format(v.intertrial_start_time))
        set_timer('state_timer', v.intertrial_duration)

    elif event == 'motion':
        delta = forward_delta_distance()
        v.iti_motion_distance += delta
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        print('{}, iti_end motion_distance={}'.format(
            get_current_time(),
            round(v.iti_motion_distance, 2),
        ))
        goto_state('trial')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')


def trial(event):
    if event == 'entry':
        v.trial_number += 1
        v.trial_start_time = get_current_time()
        v.moving_at_cue_on = moving_at_cue_on()
        print('{}, trial_start'.format(v.trial_start_time))
        print('{}, moving_at_cue_on'.format(v.moving_at_cue_on))
        print('{}, trial_condition'.format(v.trial_condition))
        print('{}, visual_gain'.format(v.visual_gain))
        print('{}, goal_distance'.format(round(v.goal_distance, 2)))
        apply_led_state(0, force=True)
        set_timer('state_timer', v.trial_timeout)

    elif event == 'motion':
        v.current_distance += forward_delta_distance()
        v.last_motion_time = get_current_time()

        if update_cues_from_progress():
            v.target_reached_time = get_current_time()
            print('{}, target_reached'.format(v.target_reached_time))
            print('{}, target_distance'.format(round(v.current_distance, 2)))
            print('{}, target_visual_progress'.format(
                round(clipped_progress(visual_progress()), 3),
            ))
            goto_state('target_wait')

    elif event == 'state_timer':
        enter_failed_trial('trial_timeout')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')


def target_wait(event):
    if event == 'entry':
        ensure_led_state(target_led_index())
        v.last_motion_time = get_current_time()
        set_timer('state_timer', v.stop_check_interval)

    elif event == 'motion':
        v.current_distance += forward_delta_distance()
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        if stop_detected():
            print('{}, stop_detected'.format(get_current_time()))
            goto_state('reward')
        elif stop_wait_timed_out():
            enter_failed_trial('stop_timeout')
        else:
            set_timer('state_timer', v.stop_check_interval)

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')


def reward(event):
    if event == 'entry':
        disarm_timer('tone_off_timer')
        hw.speaker.off()
        ensure_led_state(target_led_index())
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_delivered'.format(get_current_time()))
        print('{}, reward_number'.format(v.reward_number))
        print('{}, reward_distance'.format(round(v.current_distance, 2)))
        set_timer('state_timer', v.reward_cue_hold)

    elif event == 'state_timer':
        goto_state('intertrial')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')
        hw.speaker.off()
        set_led_baseline()


def failed_trial(event):
    if event == 'entry':
        disarm_timer('tone_off_timer')
        hw.speaker.off()
        set_led_baseline()

        if v.use_noise_penalty:
            hw.speaker.noise(v.penalty_noise_max_freq)

        set_timer('state_timer', v.failed_trial_timeout)

    elif event == 'state_timer':
        goto_state('intertrial')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')
        hw.speaker.off()


def stopped(event):
    if event == 'entry':
        hw.speaker.off()
        disarm_timer('state_timer')
        disarm_timer('tone_off_timer')
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
        stop_framework()

    elif event == 'tone_off_timer':
        hw.speaker.off()

    elif event == 'lick':
        v.lick_number += 1

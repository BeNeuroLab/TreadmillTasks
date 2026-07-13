"""Compare 5-, 7-, and 10-position LED feedback in trial blocks."""

from pyControl.utility import *
import hardware_definition as hw
from devices import *
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
v.intertrial_duration = 1 * second
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

# LED-update blocks. Conditions alternate in CSV order after a fixed number of
# completed trials (reward or failure). Reorder the CSV to change block order.
v.led_update_counts_csv = '5,7,10'
v.led_update_block_size = 20
v.led_update_conditions = []
v.led_update_condition_index = -1
v.led_update_block_number = 0
v.trial_in_led_update_block = 0
v.current_led_update_count = 0

# These reproduce the LED positions used in the 07/08 and 07/09 tasks.
v.five_led_positions_csv = '35,50,65,80,100'
v.seven_led_positions_csv = '35,46,57,68,78,89,100'
v.ten_led_positions_csv = '35,42,49,56,63,70,77,84,92,100'

# Reward availability follows the displayed LED, not continuous progress.
v.reward_zone_start_led_percent = 89
v.led_positions = []
v.num_led_positions = 0
v.current_led_index = -1
v.current_led_percent = 0

# Initial cue tone only; intermediate and target tones are disabled.
v.audio_mode = 'initial_tone_only'
v.initial_tone_freq_hz = 2000
v.initial_tone_duration = 100 * ms
v.current_tone_freq_hz = 0

# Brief outcome cues.
v.play_reward_tone = True
v.reward_tone_freq_hz = 10000
v.reward_tone_duration = 400 * ms
v.play_miss_tone = True
v.miss_noise_max_freq = 10000
v.miss_tone_duration = 200 * ms

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


def configure_led_update_conditions():
    v.led_update_conditions = parse_csv_ints(v.led_update_counts_csv)
    if not v.led_update_conditions:
        raise Exception('led_update_counts_csv must not be empty')
    for led_count in v.led_update_conditions:
        if led_count < 2:
            raise Exception('Each LED update count must be at least 2')
    if int(v.led_update_block_size) < 1:
        raise Exception('led_update_block_size must be at least 1')
    if not 1 <= int(v.reward_zone_start_led_percent) <= 100:
        raise Exception(
            'reward_zone_start_led_percent must be between 1 and 100'
        )


def evenly_spaced_led_positions(led_count):
    positions = []
    for i in range(led_count):
        fraction = i / (led_count - 1)
        positions.append(int(round(35 + (100 - 35) * fraction)))
    return positions


def configure_led_positions(led_count):
    if led_count == 5:
        v.led_positions = parse_csv_ints(v.five_led_positions_csv)
    elif led_count == 7:
        v.led_positions = parse_csv_ints(v.seven_led_positions_csv)
    elif led_count == 10:
        v.led_positions = parse_csv_ints(v.ten_led_positions_csv)
    else:
        v.led_positions = evenly_spaced_led_positions(led_count)

    v.num_led_positions = len(v.led_positions)
    if v.num_led_positions != led_count:
        raise Exception(
            'LED position list length does not match condition {}'.format(
                led_count,
            )
        )


def configure_led_update_trial():
    if (
        v.led_update_condition_index < 0
        or v.trial_in_led_update_block >= int(v.led_update_block_size)
    ):
        v.led_update_condition_index = (
            v.led_update_condition_index + 1
        ) % len(v.led_update_conditions)
        v.current_led_update_count = v.led_update_conditions[
            v.led_update_condition_index
        ]
        v.led_update_block_number += 1
        v.trial_in_led_update_block = 0
        configure_led_positions(v.current_led_update_count)
        print(
            '{}, new_led_update_block block={} led_count={} positions={}'.format(
                get_current_time(),
                v.led_update_block_number,
                v.current_led_update_count,
                v.led_positions,
            )
        )

    v.trial_in_led_update_block += 1
    print(
        '{}, led_update_trial_assigned trial={} block={} trial_in_block={} '
        'led_count={}'.format(
            get_current_time(),
            v.trial_number + 1,
            v.led_update_block_number,
            v.trial_in_led_update_block,
            v.current_led_update_count,
        )
    )


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
    if v.audio_mode != 'initial_tone_only':
        return

    if index != 0:
        return

    v.current_tone_freq_hz = v.initial_tone_freq_hz
    hw.speaker.sine(v.current_tone_freq_hz)

    set_timer('tone_off_timer', v.initial_tone_duration)
    print('{}, tone_update index={} frequency={} duration={}'.format(
        get_current_time(),
        index,
        v.current_tone_freq_hz,
        v.initial_tone_duration,
    ))


def apply_led_state(index, force=False):
    if force or index != v.current_led_index:
        set_led_state(index)
        play_tone_for_led(index)


def update_cues_from_progress(force=False):
    progress = visual_progress()
    next_index = led_index_from_progress(progress)
    apply_led_state(next_index, force)
    return progress >= 1.0


def in_reward_zone():
    return v.current_led_percent >= v.reward_zone_start_led_percent


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
    configure_led_update_trial()


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
    configure_led_update_conditions()

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
    print('{}, led_update_counts_csv'.format(v.led_update_counts_csv))
    print('{}, led_update_block_size'.format(v.led_update_block_size))
    print('{}, five_led_positions_csv'.format(v.five_led_positions_csv))
    print('{}, seven_led_positions_csv'.format(v.seven_led_positions_csv))
    print('{}, ten_led_positions_csv'.format(v.ten_led_positions_csv))
    print('{}, reward_zone_start_led_percent'.format(
        v.reward_zone_start_led_percent,
    ))
    print('{}, audio_mode'.format(v.audio_mode))
    print('{}, initial_tone_freq_hz'.format(v.initial_tone_freq_hz))
    print('{}, initial_tone_duration'.format(v.initial_tone_duration))
    print('{}, play_reward_tone'.format(v.play_reward_tone))
    print('{}, reward_tone_freq_hz'.format(v.reward_tone_freq_hz))
    print('{}, reward_tone_duration'.format(v.reward_tone_duration))
    print('{}, play_miss_tone'.format(v.play_miss_tone))
    print('{}, miss_noise_max_freq'.format(v.miss_noise_max_freq))
    print('{}, miss_tone_duration'.format(v.miss_tone_duration))
    print('{}, normal_gain'.format(v.normal_gain))
    print('{}, low_gain'.format(v.low_gain))
    print('{}, high_gain'.format(v.high_gain))
    print('{}, normal_gain_count'.format(v.normal_gain_count))
    print('{}, low_gain_count'.format(v.low_gain_count))
    print('{}, high_gain_count'.format(v.high_gain_count))
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
        print('{}, led_update_block_number'.format(v.led_update_block_number))
        print('{}, trial_in_led_update_block'.format(
            v.trial_in_led_update_block,
        ))
        print('{}, led_update_count'.format(v.current_led_update_count))
        print('{}, led_positions'.format(v.led_positions))
        print('{}, goal_distance'.format(round(v.goal_distance, 2)))
        apply_led_state(0, force=True)
        set_timer('state_timer', v.trial_timeout)

    elif event == 'motion':
        v.current_distance += forward_delta_distance()
        v.last_motion_time = get_current_time()

        update_cues_from_progress()

        if in_reward_zone():
            v.target_reached_time = get_current_time()
            print('{}, reward_zone_reached'.format(v.target_reached_time))
            print('{}, reward_zone_led_index'.format(v.current_led_index))
            print('{}, reward_zone_led_percent'.format(v.current_led_percent))
            print('{}, reward_zone_distance'.format(round(v.current_distance, 2)))
            print('{}, reward_zone_visual_progress'.format(
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
        v.last_motion_time = get_current_time()
        set_timer('state_timer', v.stop_check_interval)

    elif event == 'motion':
        v.current_distance += forward_delta_distance()
        v.last_motion_time = get_current_time()
        update_cues_from_progress()

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
        if v.play_reward_tone:
            v.current_tone_freq_hz = v.reward_tone_freq_hz
            hw.speaker.sine(v.current_tone_freq_hz)
            set_timer('tone_off_timer', v.reward_tone_duration)
            print('{}, reward_tone frequency={} duration={}'.format(
                get_current_time(),
                v.current_tone_freq_hz,
                v.reward_tone_duration,
            ))
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_delivered'.format(get_current_time()))
        print('{}, reward_number'.format(v.reward_number))
        print('{}, reward_distance'.format(round(v.current_distance, 2)))
        print('{}, reward_led_percent'.format(v.current_led_percent))
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
        try:
            hw.light.all_off()
        except Exception:
            pass

        if v.play_miss_tone:
            hw.speaker.noise(v.miss_noise_max_freq)
            set_timer('tone_off_timer', v.miss_tone_duration)
            print('{}, miss_tone reason={} max_frequency={} duration={}'.format(
                get_current_time(),
                v.failure_reason,
                v.miss_noise_max_freq,
                v.miss_tone_duration,
            ))

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

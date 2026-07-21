"""Run-to-side task with continuous center-to-side LED feedback."""

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
    'sensor_update',
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
v.stop_speed_threshold_cm_s = 2.0

# Continuous sensor polling and speed calculation.
v.sensor_update_interval = 10 * ms
v.speed_window_ms = 100
v.speed_log_interval = 100 * ms

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

# Continuous LED position and reward availability.
v.start_led_percent = 100
v.end_led_percent = 35
v.reward_zone_end_led_percent = 46
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
v.forward_sign = 1
v.moving_at_cue_window = 250 * ms
v.previous_forward_total = 0
v.rolling_speed_cm_s = 0.0
v.rolling_speed_valid = False
v.below_speed_start_time = None
v.last_above_speed_time = -1000000
v.next_speed_log_time = 0

# Trial tracking.
v.reward_number = 0
v.failure_number = 0
v.lick_number = 0
v.trial_number = 0
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


def forward_total(positive_total, negative_total):
    if v.forward_sign >= 0:
        return positive_total
    return negative_total


def sync_motion_snapshot():
    positive_total, negative_total, _, _ = (
        hw.motionSensor.get_x_motion_snapshot()
    )
    v.previous_forward_total = forward_total(
        positive_total,
        negative_total,
    )


def update_stop_speed(now, window_abs_counts, window_sample_count):
    required_samples = hw.motionSensor.continuous_window_samples
    v.rolling_speed_valid = window_sample_count >= required_samples

    if v.rolling_speed_valid:
        window_seconds = (
            window_sample_count / hw.motionSensor.data_chx.sampling_rate
        )
        v.rolling_speed_cm_s = (
            window_abs_counts / v.cpi * 2.54 / window_seconds
        )

        if v.rolling_speed_cm_s < v.stop_speed_threshold_cm_s:
            if v.below_speed_start_time is None:
                v.below_speed_start_time = now
        else:
            v.below_speed_start_time = None
            v.last_above_speed_time = now
    else:
        v.rolling_speed_cm_s = 0.0
        v.below_speed_start_time = None


def log_stop_speed(now):
    if now < v.next_speed_log_time:
        return

    if v.rolling_speed_valid:
        speed_text = round(v.rolling_speed_cm_s, 3)
    else:
        speed_text = 'warming_up'

    print('{}, rolling_speed_cm_s={}'.format(now, speed_text))
    v.next_speed_log_time = now + v.speed_log_interval


def poll_motion_sensor():
    """Update continuous displacement and speed; return forward distance."""
    positive_total, negative_total, window_abs_counts, window_samples = (
        hw.motionSensor.get_x_motion_snapshot()
    )
    current_forward_total = forward_total(
        positive_total,
        negative_total,
    )
    forward_counts = current_forward_total - v.previous_forward_total
    v.previous_forward_total = current_forward_total

    if forward_counts < 0:
        forward_counts = 0

    now = get_current_time()
    update_stop_speed(now, window_abs_counts, window_samples)
    log_stop_speed(now)

    return forward_counts / v.cpi * 2.54


def visual_progress():
    if v.goal_distance <= 0:
        return 1.0
    return v.current_distance * v.visual_gain / v.goal_distance


def led_percent_from_progress(progress):
    led_range = v.start_led_percent - v.end_led_percent
    led_percent = v.start_led_percent - int(
        clipped_progress(progress) * led_range
    )
    return max(
        v.end_led_percent,
        min(v.start_led_percent, led_percent),
    )


def set_led_baseline():
    try:
        hw.light.all_red()
    except Exception:
        pass


def set_led_state(led_percent):
    v.current_led_percent = led_percent
    try:
        hw.light.cue(v.current_led_percent)
    except Exception:
        pass

    print('{}, led_update percent={} visual_progress={}'.format(
        get_current_time(),
        v.current_led_percent,
        round(clipped_progress(visual_progress()), 3),
    ))


def play_initial_tone():
    if v.audio_mode != 'initial_tone_only':
        return

    v.current_tone_freq_hz = v.initial_tone_freq_hz
    hw.speaker.sine(v.current_tone_freq_hz)
    set_timer('tone_off_timer', v.initial_tone_duration)
    print('{}, tone_update frequency={} duration={}'.format(
        get_current_time(),
        v.current_tone_freq_hz,
        v.initial_tone_duration,
    ))


def update_cues_from_progress(force=False):
    led_percent = led_percent_from_progress(visual_progress())
    if force or led_percent != v.current_led_percent:
        set_led_state(led_percent)


def in_reward_zone():
    return v.current_led_percent <= v.reward_zone_end_led_percent


def reset_trial_variables():
    v.current_distance = 0
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
    return (
        v.rolling_speed_valid
        and v.below_speed_start_time is not None
        and get_current_time() - v.below_speed_start_time
        >= v.reward_wait_time
    )


def moving_at_cue_on():
    return (
        get_current_time() - v.last_above_speed_time
        <= v.moving_at_cue_window
    )


def schedule_sensor_update():
    set_timer('sensor_update', v.sensor_update_interval)


# -------------------------------------------------------------------------
# Run start/end
# -------------------------------------------------------------------------
def run_start():
    if v.sensor_update_interval <= 0:
        raise Exception('sensor_update_interval must be positive')
    if v.speed_window_ms <= 0:
        raise Exception('speed_window_ms must be positive')
    if v.stop_speed_threshold_cm_s <= 0:
        raise Exception('stop_speed_threshold_cm_s must be positive')
    if not 1 <= v.end_led_percent < v.start_led_percent <= 100:
        raise Exception('Continuous LED range must be within 1 to 100')
    if not (
        v.end_led_percent
        <= v.reward_zone_end_led_percent
        <= v.start_led_percent
    ):
        raise Exception('Reward-zone LED percent must be inside LED range')

    hw.speaker.set_volume(15)
    hw.speaker.off()
    hw.motionSensor.configure_continuous_motion(v.speed_window_ms)
    hw.motionSensor.record()
    hw.reward.reward_duration = v.reward_duration

    try:
        hw.light.start()
        hw.light.all_red()
        hw.light.cue_bilateral(True)
        hw.light.send_int(212)  # set BIG_LED=True
    except Exception:
        pass

    if hw.motionSensor.sensor_x is None:
        raise Exception('Motion sensor CPI unavailable; sensor_x not initialized')
    v.cpi = hw.motionSensor.sensor_x.CPI
    sync_motion_snapshot()

    print('{}, CPI'.format(v.cpi))
    print('{}, forward_sign'.format(v.forward_sign))
    print('{}, sensor_update_interval'.format(v.sensor_update_interval))
    print('{}, requested_speed_window_ms'.format(v.speed_window_ms))
    print('{}, actual_speed_window_ms'.format(
        hw.motionSensor.continuous_window_ms,
    ))
    print('{}, speed_window_samples'.format(
        hw.motionSensor.continuous_window_samples,
    ))
    print('{}, stop_speed_threshold_cm_s'.format(
        v.stop_speed_threshold_cm_s,
    ))
    print('{}, reward_wait_time'.format(v.reward_wait_time))
    print('{}, session_duration'.format(v.session_duration))
    print('{}, intertrial_duration'.format(v.intertrial_duration))
    print('{}, trial_timeout'.format(v.trial_timeout))
    print('{}, reward_duration'.format(v.reward_duration))
    print('{}, stop_to_reward_timeout'.format(v.stop_to_reward_timeout))
    print('{}, goal_distance_base'.format(v.goal_distance_base))
    print('{}, goal_distance_jitter'.format(v.goal_distance_jitter))
    print('{}, start_led_percent'.format(v.start_led_percent))
    print('{}, end_led_percent'.format(v.end_led_percent))
    print('{}, reward_zone_end_led_percent'.format(
        v.reward_zone_end_led_percent,
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
        v.next_speed_log_time = v.intertrial_start_time
        sync_motion_snapshot()
        print('{}, iti_start'.format(v.intertrial_start_time))
        set_timer('state_timer', v.intertrial_duration)
        schedule_sensor_update()

    elif event == 'sensor_update':
        v.iti_motion_distance += poll_motion_sensor()
        schedule_sensor_update()

    elif event == 'state_timer':
        v.iti_motion_distance += poll_motion_sensor()
        print('{}, iti_end motion_distance={}'.format(
            get_current_time(),
            round(v.iti_motion_distance, 2),
        ))
        goto_state('trial')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')
        disarm_timer('sensor_update')


def trial(event):
    if event == 'entry':
        v.trial_number += 1
        v.trial_start_time = get_current_time()
        v.moving_at_cue_on = moving_at_cue_on()
        v.below_speed_start_time = None
        print('{}, trial_start'.format(v.trial_start_time))
        print('{}, moving_at_cue_on'.format(v.moving_at_cue_on))
        print('{}, trial_condition'.format(v.trial_condition))
        print('{}, visual_gain'.format(v.visual_gain))
        print('{}, continuous_led_feedback'.format(True))
        print('{}, continuous_led_direction=center_to_side'.format(
            get_current_time(),
        ))
        print('{}, goal_distance'.format(round(v.goal_distance, 2)))
        update_cues_from_progress(force=True)
        play_initial_tone()
        set_timer('state_timer', v.trial_timeout)
        schedule_sensor_update()

    elif event == 'sensor_update':
        v.current_distance += poll_motion_sensor()
        update_cues_from_progress()

        if in_reward_zone():
            v.target_reached_time = get_current_time()
            print('{}, reward_zone_reached'.format(v.target_reached_time))
            print('{}, reward_zone_led_percent'.format(v.current_led_percent))
            print('{}, reward_zone_distance'.format(round(v.current_distance, 2)))
            print('{}, reward_zone_visual_progress'.format(
                round(clipped_progress(visual_progress()), 3),
            ))
            goto_state('target_wait')
        else:
            schedule_sensor_update()

    elif event == 'state_timer':
        enter_failed_trial('trial_timeout')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')
        disarm_timer('sensor_update')


def target_wait(event):
    if event == 'entry':
        set_timer('state_timer', v.stop_to_reward_timeout)
        schedule_sensor_update()

    elif event == 'sensor_update':
        v.current_distance += poll_motion_sensor()
        update_cues_from_progress()

        if stop_detected():
            print('{}, stop_detected speed_cm_s={} below_since={}'.format(
                get_current_time(),
                round(v.rolling_speed_cm_s, 3),
                v.below_speed_start_time,
            ))
            goto_state('reward')
        else:
            schedule_sensor_update()

    elif event == 'state_timer':
        enter_failed_trial('stop_timeout')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')
        disarm_timer('sensor_update')


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
        set_led_baseline()

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
        disarm_timer('sensor_update')
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


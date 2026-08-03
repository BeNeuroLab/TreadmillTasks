"""Run-to-center task with slower continuous LED gain in the reward zone."""

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
v.initiation_timeout = 5 * second
v.performance_timeout = 5 * second
v.initiation_distance_cm = 3
v.reward_cue_hold = 0.5 * second

# Reward and stopping rule.
v.reward_duration = 30 * ms
v.reward_wait_time = 250 * ms
v.stop_speed_threshold_cm_s = 5.0

# Continuous sensor polling and speed calculation.
v.sensor_update_interval = 10 * ms
v.speed_window_ms = 50

# Distance and visual gain.
v.goal_distance_base = 60
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
v.start_led_percent = 0
v.end_led_percent = 100
v.reward_zone_start_progress = 0.70
v.reward_zone_gain_multiplier = 0.5
v.current_led_percent = 0

# Fixed auditory cues: one initial tone and one reward tone.
v.initial_tone_freq_hz = 2000
v.initial_tone_duration = 100 * ms
v.reward_tone_freq_hz = 10000
v.reward_tone_duration = 400 * ms

# Motion sensor.
v.cpi = None
v.forward_sign = 1
v.moving_at_cue_window = 250 * ms
v.previous_forward_total = 0
v.rolling_speed_cm_s = 0.0
v.rolling_speed_valid = False
v.below_speed_start_time = None
v.last_above_speed_time = -1000000

# Trial tracking.
v.reward_number = 0
v.failure_number = 0
v.lick_number = 0
v.trial_number = 0
v.intertrial_start_time = 0
v.trial_start_time = 0
v.initiation_time = 0
v.target_reached_time = 0
v.iti_motion_distance = 0
v.moving_at_cue_on = False
v.trial_phase = 'initiation'


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
        print('{}, new_gain_block'.format(get_current_time()))
        print('{}, gain_block_number'.format(v.gain_block_number))
        print('{}, gain_block_order'.format(
            '|'.join(v.gain_trial_queue),
        ))

    v.trial_condition = v.gain_trial_queue.pop(0)

    if v.trial_condition == 'low':
        v.visual_gain = v.low_gain
    elif v.trial_condition == 'high':
        v.visual_gain = v.high_gain
    else:
        v.trial_condition = 'normal'
        v.visual_gain = v.normal_gain


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

    return forward_counts / v.cpi * 2.54


def visual_progress():
    if v.goal_distance <= 0:
        return 1.0

    zone_entry_distance = (
        v.reward_zone_start_progress
        * v.goal_distance
        / v.visual_gain
    )
    if v.current_distance <= zone_entry_distance:
        return v.current_distance * v.visual_gain / v.goal_distance

    reward_zone_distance = v.current_distance - zone_entry_distance
    reward_zone_gain = (
        v.visual_gain * v.reward_zone_gain_multiplier
    )
    return (
        v.reward_zone_start_progress
        + reward_zone_distance * reward_zone_gain / v.goal_distance
    )


def led_percent_from_progress(progress):
    led_range = v.end_led_percent - v.start_led_percent
    led_percent = v.start_led_percent + int(
        clipped_progress(progress) * led_range
    )
    return max(
        1,
        min(v.end_led_percent, led_percent),
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


def play_initial_tone():
    hw.speaker.sine(v.initial_tone_freq_hz)
    set_timer('tone_off_timer', v.initial_tone_duration)
    print('{}, initial_tone'.format(get_current_time()))


def update_cues_from_progress(force=False):
    led_percent = led_percent_from_progress(visual_progress())
    if force or led_percent != v.current_led_percent:
        set_led_state(led_percent)


def in_reward_zone():
    progress = visual_progress()
    return v.reward_zone_start_progress <= progress <= 1.0


def beyond_reward_zone():
    return visual_progress() > 1.0


def reset_trial_variables():
    v.current_distance = 0
    v.current_led_percent = 0
    v.target_reached_time = 0
    v.trial_start_time = 0
    v.initiation_time = 0
    v.trial_phase = 'initiation'
    configure_gain_trial()


def record_failure(reason):
    v.failure_number += 1
    print('{}, trial_failure'.format(get_current_time()))
    print('{}, trial_failure_reason'.format(reason))
    print('{}, trial_failure_distance_cm'.format(
        round(v.current_distance, 2),
    ))
    print('{}, trial_failure_visual_progress'.format(
        round(visual_progress(), 3),
    ))
    goto_state('intertrial')


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
    if not 0 < v.reward_zone_start_progress < 1:
        raise Exception('reward_zone_start_progress must be between 0 and 1')
    if not 0 < v.reward_zone_gain_multiplier <= 1:
        raise Exception(
            'reward_zone_gain_multiplier must be greater than 0 and at most 1'
        )
    if min(v.normal_gain, v.low_gain, v.high_gain) <= 0:
        raise Exception('All visual gains must be positive')
    if v.initiation_distance_cm <= 0:
        raise Exception('initiation_distance_cm must be positive')
    if v.initiation_timeout <= 0 or v.performance_timeout <= 0:
        raise Exception('Initiation and performance timeouts must be positive')
    if not 0 <= v.start_led_percent < v.end_led_percent <= 100:
        raise Exception('Continuous LED range must be within 0 to 100')

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
    print('{}, speed_window_ms'.format(v.speed_window_ms))
    print('{}, stop_speed_threshold_cm_s'.format(
        v.stop_speed_threshold_cm_s,
    ))
    print('{}, reward_wait_time_ms'.format(v.reward_wait_time))
    print('{}, motion_sampling_rate_hz'.format(
        hw.motionSensor.data_chx.sampling_rate,
    ))
    print('{}, forward_sign'.format(v.forward_sign))
    print('{}, initial_tone_freq_hz'.format(v.initial_tone_freq_hz))
    print('{}, initial_tone_duration_ms'.format(v.initial_tone_duration))
    print('{}, reward_tone_freq_hz'.format(v.reward_tone_freq_hz))
    print('{}, reward_tone_duration_ms'.format(v.reward_tone_duration))
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
        sync_motion_snapshot()
        print('{}, iti_start'.format(v.intertrial_start_time))
        set_timer('state_timer', v.intertrial_duration)
        schedule_sensor_update()

    elif event == 'sensor_update':
        v.iti_motion_distance += poll_motion_sensor()
        schedule_sensor_update()

    elif event == 'state_timer':
        v.iti_motion_distance += poll_motion_sensor()
        print('{}, iti_end'.format(get_current_time()))
        print('{}, iti_motion_distance_cm'.format(
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
        print('{}, reward_zone_gain_multiplier'.format(
            v.reward_zone_gain_multiplier,
        ))
        print('{}, reward_zone_effective_gain'.format(
            v.visual_gain * v.reward_zone_gain_multiplier,
        ))
        print('{}, continuous_led_feedback'.format(True))
        print('{}, goal_distance'.format(round(v.goal_distance, 2)))
        update_cues_from_progress(force=True)
        play_initial_tone()
        set_timer('state_timer', v.initiation_timeout)
        schedule_sensor_update()

    elif event == 'sensor_update':
        v.current_distance += poll_motion_sensor()

        if (
            v.trial_phase == 'initiation'
            and v.current_distance >= v.initiation_distance_cm
        ):
            v.trial_phase = 'performance'
            v.initiation_time = get_current_time()
            print('{}, trial_initiated'.format(v.initiation_time))
            print('{}, trial_initiation_distance_cm'.format(
                round(v.current_distance, 2),
            ))
            print('{}, trial_initiation_latency_ms'.format(
                v.initiation_time - v.trial_start_time,
            ))
            reset_timer('state_timer', v.performance_timeout)

        if v.trial_phase == 'performance' and beyond_reward_zone():
            set_led_baseline()
            record_failure('overshoot')
        else:
            update_cues_from_progress()

            if v.trial_phase == 'performance' and in_reward_zone():
                v.target_reached_time = get_current_time()
                print('{}, reward_zone_reached'.format(v.target_reached_time))
                print('{}, reward_zone_led_percent'.format(
                    v.current_led_percent,
                ))
                print('{}, reward_zone_distance'.format(
                    round(v.current_distance, 2),
                ))
                print('{}, reward_zone_visual_progress'.format(
                    round(visual_progress(), 3),
                ))
                goto_state('target_wait')
            else:
                schedule_sensor_update()

    elif event == 'state_timer':
        if v.trial_phase == 'initiation':
            record_failure('initiation_timeout')
        else:
            record_failure('performance_timeout')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')
        disarm_timer('sensor_update')


def target_wait(event):
    if event == 'entry':
        schedule_sensor_update()

    elif event == 'sensor_update':
        v.current_distance += poll_motion_sensor()

        if beyond_reward_zone():
            set_led_baseline()
            record_failure('overshoot')
        else:
            update_cues_from_progress()

            if stop_detected():
                print('{}, stop_detected'.format(get_current_time()))
                print('{}, stop_detected_speed_cm_s'.format(
                    round(v.rolling_speed_cm_s, 3),
                ))
                goto_state('reward')
            else:
                schedule_sensor_update()

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('sensor_update')


def reward(event):
    if event == 'entry':
        disarm_timer('tone_off_timer')
        hw.speaker.off()
        hw.speaker.sine(v.reward_tone_freq_hz)
        set_timer('tone_off_timer', v.reward_tone_duration)
        print('{}, reward_tone'.format(get_current_time()))
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

"""Run a short distance, stop below a speed threshold, and receive reward."""

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import utime


# -------------------------------------------------------------------------
# States and events
# -------------------------------------------------------------------------
states = [
    'intertrial',
    'trial',
    'wait_for_stop',
    'reward',
    'miss',
    'stopped',
]

events = [
    'session_timer',
    'state_timer',
    'response_timer',
    'sensor_update',
    'lick',
    'stop_button',
]

initial_state = 'intertrial'


# -------------------------------------------------------------------------
# Task variables
# -------------------------------------------------------------------------
# Session timing.
v.session_duration = 30 * minute
v.intertrial_duration = 2 * second
v.response_window = 3 * second
v.miss_reset_duration = 0.5 * second

# Reward and speed-based stop rule.
v.reward_duration = 30 * ms
v.reward_led_hold = 0.5 * second
v.stop_hold_duration = 300 * ms
v.stop_speed_threshold_cm_s = 2.0

# Continuous sensor polling and speed calculation.
v.sensor_update_interval = 10 * ms
v.speed_window_ms = 100
v.speed_log_interval = 100 * ms

# Distance and stimulus.
v.target_distance = 30
v.max_post_cue_distance = 10
v.current_distance = 0
v.cpi = None
v.forward_sign = 1
v.target_led_percent = 100

# Tone controls.
v.play_reward_tone = False
v.reward_tone_freq_hz = 10000
v.play_miss_tone = False
v.miss_tone_freq_hz = 4000

# Motion sensor state.
v.previous_forward_total = 0
v.rolling_speed_cm_s = 0.0
v.rolling_speed_valid = False
v.below_speed_start_time = None
v.next_speed_log_time = 0

# Trial tracking.
v.reward_number = 0
v.miss_number = 0
v.lick_number = 0
v.target_reached_time = 0
v.cue_presented_distance = 0
v.miss_reason = ''


# -------------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------------
def set_led_baseline():
    try:
        hw.light.all_red()
    except Exception:
        pass


def set_target_led():
    try:
        hw.light.cue(v.target_led_percent)
    except Exception:
        pass


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

    if not v.rolling_speed_valid:
        v.rolling_speed_cm_s = 0.0
        v.below_speed_start_time = None
        return

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


def stop_detected():
    return (
        v.rolling_speed_valid
        and v.below_speed_start_time is not None
        and get_current_time() - v.below_speed_start_time
        >= v.stop_hold_duration
    )


def post_cue_distance():
    return max(0, v.current_distance - v.cue_presented_distance)


def distance_limit_reached():
    return post_cue_distance() >= v.max_post_cue_distance


def schedule_sensor_update():
    set_timer('sensor_update', v.sensor_update_interval)


def enter_miss(reason):
    v.miss_number += 1
    v.miss_reason = reason
    print('{}, miss_number'.format(v.miss_number))
    print('{}, miss_reason'.format(reason))
    print('{}, miss_distance'.format(round(v.current_distance, 2)))
    goto_state('miss')


# -------------------------------------------------------------------------
# Framework hooks
# -------------------------------------------------------------------------
def run_start():
    if v.sensor_update_interval <= 0:
        raise Exception('sensor_update_interval must be positive')
    if v.speed_window_ms <= 0:
        raise Exception('speed_window_ms must be positive')
    if v.stop_speed_threshold_cm_s <= 0:
        raise Exception('stop_speed_threshold_cm_s must be positive')
    if v.stop_hold_duration <= 0:
        raise Exception('stop_hold_duration must be positive')
    if v.max_post_cue_distance <= 0:
        raise Exception('max_post_cue_distance must be positive')

    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.configure_continuous_motion(v.speed_window_ms)
    hw.motionSensor.record()
    hw.speaker.set_volume(10)
    hw.speaker.off()

    try:
        hw.light.start()
        utime.sleep_ms(20)
        hw.light.cue_bilateral(True)
        hw.light.send_int(212)  # set BIG_LED=True
        hw.light.all_red()
    except Exception:
        pass

    if hw.motionSensor.sensor_x is None:
        raise Exception('Motion sensor CPI unavailable; sensor_x not initialized')
    v.cpi = hw.motionSensor.sensor_x.CPI
    sync_motion_snapshot()

    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(v.cpi))
    print('{}, distance_axis'.format('x'))
    print('{}, distance_units'.format('cm'))
    print('{}, forward_sign'.format(v.forward_sign))
    print('{}, target_distance'.format(v.target_distance))
    print('{}, max_post_cue_distance'.format(v.max_post_cue_distance))
    print('{}, target_led_percent'.format(v.target_led_percent))
    print('{}, sensor_update_interval'.format(v.sensor_update_interval))
    print('{}, speed_window_ms'.format(v.speed_window_ms))
    print('{}, stop_speed_threshold_cm_s'.format(
        v.stop_speed_threshold_cm_s,
    ))
    print('{}, stop_hold_duration'.format(v.stop_hold_duration))
    print('{}, response_window'.format(v.response_window))
    print('{}, reward_duration'.format(v.reward_duration))
    print('{}, reward_led_hold'.format(v.reward_led_hold))
    print('{}, play_reward_tone'.format(v.play_reward_tone))
    print('{}, reward_tone_frequency'.format(v.reward_tone_freq_hz))
    print('{}, play_miss_tone'.format(v.play_miss_tone))
    print('{}, miss_tone_frequency'.format(v.miss_tone_freq_hz))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()


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
    print('{}, total_misses'.format(v.miss_number))
    print('{}, total_licks'.format(v.lick_number))
    print('Session Ended')


# -------------------------------------------------------------------------
# State machine
# -------------------------------------------------------------------------
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        set_led_baseline()
        v.current_distance = 0
        v.target_reached_time = 0
        v.cue_presented_distance = 0
        v.miss_reason = ''
        v.below_speed_start_time = None
        v.next_speed_log_time = get_current_time()
        sync_motion_snapshot()
        print('{}, intertrial_start'.format(get_current_time()))
        set_timer('state_timer', v.intertrial_duration)
        schedule_sensor_update()

    elif event == 'sensor_update':
        poll_motion_sensor()
        schedule_sensor_update()

    elif event == 'state_timer':
        goto_state('trial')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')
        disarm_timer('sensor_update')


def trial(event):
    if event == 'entry':
        v.current_distance = 0
        v.below_speed_start_time = None
        set_led_baseline()
        hw.speaker.off()
        sync_motion_snapshot()
        print('{}, trial_start'.format(get_current_time()))
        schedule_sensor_update()

    elif event == 'sensor_update':
        v.current_distance += poll_motion_sensor()

        if v.current_distance >= v.target_distance:
            v.target_reached_time = get_current_time()
            v.cue_presented_distance = v.current_distance
            v.below_speed_start_time = None
            set_target_led()
            print('{}, target_reached'.format(v.target_reached_time))
            print('{}, target_distance'.format(v.target_distance))
            print('{}, current_distance'.format(round(v.current_distance, 2)))
            print('{}, cue_presented_distance'.format(
                round(v.cue_presented_distance, 2),
            ))
            goto_state('wait_for_stop')
        else:
            schedule_sensor_update()

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('sensor_update')


def wait_for_stop(event):
    if event == 'entry':
        set_timer('response_timer', v.response_window)
        schedule_sensor_update()

    elif event == 'sensor_update':
        v.current_distance += poll_motion_sensor()

        if distance_limit_reached():
            print('{}, post_cue_distance={}'.format(
                get_current_time(),
                round(post_cue_distance(), 2),
            ))
            enter_miss('distance_limit')
        elif stop_detected():
            print('{}, stop_success speed_cm_s={} below_since={}'.format(
                get_current_time(),
                round(v.rolling_speed_cm_s, 3),
                v.below_speed_start_time,
            ))
            goto_state('reward')
        else:
            schedule_sensor_update()

    elif event == 'response_timer':
        enter_miss('stop_timeout')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('sensor_update')
        disarm_timer('response_timer')


def reward(event):
    if event == 'entry':
        set_target_led()
        if v.play_reward_tone:
            hw.speaker.sine(v.reward_tone_freq_hz)
        else:
            hw.speaker.off()

        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        print('{}, reward_speed_cm_s'.format(
            round(v.rolling_speed_cm_s, 3),
        ))
        set_timer('state_timer', v.reward_led_hold)

    elif event == 'state_timer':
        goto_state('intertrial')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        hw.speaker.off()
        set_led_baseline()
        disarm_timer('state_timer')


def miss(event):
    if event == 'entry':
        set_led_baseline()
        if v.play_miss_tone:
            hw.speaker.sine(v.miss_tone_freq_hz)
            print('{}, miss_tone_frequency'.format(v.miss_tone_freq_hz))
        else:
            hw.speaker.off()
        set_timer('state_timer', v.miss_reset_duration)

    elif event == 'state_timer':
        goto_state('intertrial')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        hw.speaker.off()
        disarm_timer('state_timer')


def stopped(event):
    if event == 'entry':
        hw.speaker.off()
        disarm_timer('state_timer')
        disarm_timer('response_timer')
        disarm_timer('sensor_update')
        try:
            hw.light.all_off()
        except Exception:
            pass

    elif event == 'stop_button':
        goto_state('intertrial')


def all_states(event):
    if event == 'session_timer':
        print('Session Timer Expired - Stopping Framework')
        stop_framework()

    elif event == 'lick':
        v.lick_number += 1

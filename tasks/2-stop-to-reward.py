"""Run a short distance, stop at center LED, then receive automatic reward."""

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
    'motion',
    'lick',
    'stop_button',
]

initial_state = 'intertrial'


# -------------------------------------------------------------------------
# Task variables
# -------------------------------------------------------------------------
# Session timing
v.session_duration = 30 * minute
v.intertrial_duration = 2 * second
v.response_window = 10 * second
v.miss_reset_duration = 0.5 * second

# Reward and stop rule
v.reward_duration = 30 * ms
v.reward_led_hold = 0.5 * second
v.stop_hold_duration = 300 * ms
v.stop_check_interval = 50 * ms

# Distance and stimulus
v.target_distance = 30
v.current_distance = 0
v.motion_threshold = 2
v.cpi = None
v.forward_sign = 1
v.target_led_percent = 100

# Tone controls
v.play_reward_tone = False
v.reward_tone_freq_hz = 10000
v.play_miss_tone = False
v.miss_tone_freq_hz = 4000

# Trial tracking
v.reward_number = 0
v.miss_number = 0
v.lick_number = 0
v.last_motion_time = 0
v.target_reached_time = 0
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


def hold_complete():
    return get_current_time() - v.last_motion_time >= v.stop_hold_duration


def response_timed_out():
    return get_current_time() - v.target_reached_time >= v.response_window


def forward_delta_distance():
    """Return positive x-axis motion since the last motion event in cm."""
    if v.cpi is None:
        raise Exception('Motion sensor CPI unavailable')

    forward_counts = v.forward_sign * hw.motionSensor.x
    if forward_counts < 0:
        forward_counts = 0

    return forward_counts / v.cpi * 2.54


def enter_miss(reason):
    v.miss_number += 1
    v.miss_reason = reason
    print('{}, miss_number'.format(v.miss_number))
    print('{}, miss_reason'.format(reason))
    print('{}, miss_distance'.format(v.current_distance))
    goto_state('miss')


# -------------------------------------------------------------------------
# Framework hooks
# -------------------------------------------------------------------------
def run_start():
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_threshold
    hw.speaker.set_volume(10)
    hw.speaker.off()

    try:
        hw.light.start()
        utime.sleep_ms(20)
        hw.light.cue_bilateral(True)
        hw.light.all_red()
    except Exception:
        pass

    if hw.motionSensor.sensor_x is None:
        raise Exception('Motion sensor CPI unavailable; sensor_x not initialized')
    v.cpi = hw.motionSensor.sensor_x.CPI

    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(v.cpi))
    print('{}, motion_threshold'.format(v.motion_threshold))
    print('{}, distance_axis'.format('x'))
    print('{}, distance_units'.format('cm'))
    print('{}, forward_sign'.format(v.forward_sign))
    print('{}, target_distance'.format(v.target_distance))
    print('{}, target_led_percent'.format(v.target_led_percent))
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
        v.last_motion_time = 0
        v.target_reached_time = 0
        v.miss_reason = ''
        print('{}, intertrial_start'.format(get_current_time()))
        set_timer('state_timer', v.intertrial_duration)

    elif event == 'state_timer':
        goto_state('trial')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')


def trial(event):
    if event == 'entry':
        v.current_distance = 0
        set_led_baseline()
        hw.speaker.off()
        print('{}, trial_start'.format(get_current_time()))

    elif event == 'motion':
        v.current_distance += forward_delta_distance()

        if v.current_distance >= v.target_distance:
            v.target_reached_time = get_current_time()
            v.last_motion_time = get_current_time()
            set_target_led()
            print('{}, target_reached'.format(v.target_reached_time))
            print('{}, target_distance'.format(v.target_distance))
            print('{}, current_distance'.format(round(v.current_distance, 2)))
            goto_state('wait_for_stop')

    elif event == 'stop_button':
        goto_state('stopped')


def wait_for_stop(event):
    if event == 'entry':
        set_timer('state_timer', v.stop_check_interval)
        set_timer('response_timer', v.response_window)

    elif event == 'motion':
        v.current_distance += forward_delta_distance()
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        if hold_complete():
            print('{}, stop_success'.format(get_current_time()))
            goto_state('reward')
        elif response_timed_out():
            enter_miss('stop_timeout')
        else:
            set_timer('state_timer', v.stop_check_interval)

    elif event == 'response_timer':
        enter_miss('stop_timeout')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')
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

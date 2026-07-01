"""LED-only center-to-side spatial stopping task.

Run to the visual landmark, stop inside the spatial reward zone, hold, reward.
"""

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
    'zone_check',
    'reward',
    'miss',
    'stopped',
]

events = [
    'session_timer',
    'state_timer',
    'motion',
    'lick',
    'stop_button',
]

initial_state = 'intertrial'


# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session parameters
v.session_duration = 30 * minute

# Trial timing
v.intertrial_duration = 2 * second
v.trial_timeout = 15 * second
v.miss_reset_duration = 0.5 * second
v.reward_post_delay = 0.5 * second

# Reward and stopping rule
v.reward_duration = 35 * ms
v.reward_wait_time = 0.5 * second
v.stop_to_reward_timeout = 1.5 * second
v.reward_zone_before = 5
v.reward_zone_after = 10

# Distance mapping
v.goal_distance_base = 60
v.goal_distance_jitter = 0.20
v.goal_distance = v.goal_distance_base
v.current_distance = 0
v.side_buffer_after_zone = 5
v.zone_start_distance = v.goal_distance_base - v.reward_zone_before
v.zone_end_distance = v.goal_distance_base + v.reward_zone_after
v.track_end_distance = v.zone_end_distance + v.side_buffer_after_zone

# LED-only landmark mapping: center -> side.
# Cue width is controlled by LED strip firmware; this task sends position only.
v.start_led_percent = 100
v.side_led_percent = 3
v.current_led_percent = None

# Optional outcome tone, off by default for LED-only behavior.
v.play_goal_tone = False
v.goal_freq_hz = 10000

# Motion sensor parameters
v.cpi = None
v.motion_threshold = 3
v.forward_sign = 1
v.print_motion_debug = False

# Trial tracking
v.reward_number = 0
v.miss_number = 0
v.lick_number = 0
v.last_motion_time = 0
v.intertrial_start_time = 0
v.zone_entry_time = 0
v.miss_reason = ''


# -------------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------------
def clipped_progress(progress):
    return max(0.0, min(1.0, progress))


def led_percent_from_distance(distance):
    """Map distance along the visual track to LED strip percent."""
    p = clipped_progress(distance / v.track_end_distance)
    percent = int(
        v.start_led_percent
        - ((v.start_led_percent - v.side_led_percent) * p)
    )
    return max(v.side_led_percent, min(v.start_led_percent, percent))


def forward_delta_cm():
    """Return forward x-axis motion since the last motion event in cm."""
    if v.cpi is None:
        raise Exception('Motion sensor CPI unavailable')

    dx = hw.motionSensor.x
    dy = hw.motionSensor.y

    if v.print_motion_debug:
        print('{}, motion_dx={}, motion_dy={}'.format(
            get_current_time(),
            dx,
            dy,
        ))

    forward_counts = v.forward_sign * dx
    if forward_counts < 0:
        forward_counts = 0

    return forward_counts / v.cpi * 2.54


def update_landmark_from_distance(force=False):
    """Update LED landmark position from current distance."""
    led_p = led_percent_from_distance(v.current_distance)

    if force or led_p != v.current_led_percent:
        v.current_led_percent = led_p
        try:
            hw.light.cue(led_p)
        except Exception:
            pass


def reset_trial():
    """Reset distance and generate this trial's spatial reward zone."""
    v.current_distance = 0
    v.current_led_percent = None
    v.last_motion_time = 0
    v.zone_entry_time = 0
    v.miss_reason = ''

    jitter_fraction = 1 + random.uniform(
        -v.goal_distance_jitter,
        v.goal_distance_jitter,
    )
    v.goal_distance = v.goal_distance_base * jitter_fraction
    v.zone_start_distance = max(0, v.goal_distance - v.reward_zone_before)
    v.zone_end_distance = v.goal_distance + v.reward_zone_after
    v.track_end_distance = v.zone_end_distance + v.side_buffer_after_zone

    print('{}, new_goal_distance'.format(round(v.goal_distance, 2)))
    print('{}, reward_zone_start'.format(round(v.zone_start_distance, 2)))
    print('{}, reward_zone_end'.format(round(v.zone_end_distance, 2)))
    print('{}, track_end_distance'.format(round(v.track_end_distance, 2)))
    print('{}, goal_led_percent'.format(
        led_percent_from_distance(v.goal_distance),
    ))


def enter_miss(reason):
    v.miss_number += 1
    v.miss_reason = reason
    print('{}, miss_number'.format(v.miss_number))
    print('{}, miss_reason={}'.format(get_current_time(), reason))
    goto_state('miss')


def in_reward_zone():
    return (
        v.current_distance >= v.zone_start_distance
        and v.current_distance <= v.zone_end_distance
    )


def beyond_reward_zone():
    return v.current_distance > v.zone_end_distance


def hold_complete():
    return get_current_time() - v.last_motion_time >= v.reward_wait_time


def zone_check_timed_out():
    return get_current_time() - v.zone_entry_time >= v.stop_to_reward_timeout


# -------------------------------------------------------------------------
# Run start/end
# -------------------------------------------------------------------------
def run_start():
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
    print('{}, print_motion_debug'.format(v.print_motion_debug))
    print('{}, session_duration'.format(v.session_duration))
    print('{}, intertrial_duration'.format(v.intertrial_duration))
    print('{}, trial_timeout'.format(v.trial_timeout))
    print('{}, reward_wait_time'.format(v.reward_wait_time))
    print('{}, stop_to_reward_timeout'.format(v.stop_to_reward_timeout))
    print('{}, reward_zone_before'.format(v.reward_zone_before))
    print('{}, reward_zone_after'.format(v.reward_zone_after))
    print('{}, side_buffer_after_zone'.format(v.side_buffer_after_zone))
    print('{}, base_goal_distance'.format(v.goal_distance_base))
    print('{}, goal_jitter_fraction'.format(v.goal_distance_jitter))
    print('{}, start_led_percent'.format(v.start_led_percent))
    print('{}, side_led_percent'.format(v.side_led_percent))
    print('{}, play_goal_tone'.format(v.play_goal_tone))
    print('{}, before_camera_trigger'.format(get_current_time()))

    hw.cameraTrigger.start()
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
        try:
            hw.light.all_red()
        except Exception:
            pass
        reset_trial()
        v.intertrial_start_time = get_current_time()
        set_timer('state_timer', v.intertrial_duration)

    elif event == 'state_timer':
        goto_state('trial')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')


def trial(event):
    if event == 'entry':
        disarm_timer('state_timer')
        print('{}, trial_start'.format(get_current_time()))
        update_landmark_from_distance(force=True)
        set_timer('state_timer', v.trial_timeout)

    elif event == 'motion':
        v.current_distance += forward_delta_cm()
        v.last_motion_time = get_current_time()
        update_landmark_from_distance()

        if beyond_reward_zone():
            enter_miss('overshot_zone')
        elif v.current_distance >= v.zone_start_distance:
            goto_state('zone_check')

    elif event == 'state_timer':
        enter_miss('trial_timeout')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')


def zone_check(event):
    if event == 'entry':
        v.zone_entry_time = get_current_time()
        v.last_motion_time = get_current_time()
        print('{}, zone_entry'.format(get_current_time()))
        print('{}, zone_entry_distance'.format(v.current_distance))
        update_landmark_from_distance(force=True)
        set_timer('state_timer', 50 * ms)

    elif event == 'motion':
        v.current_distance += forward_delta_cm()
        v.last_motion_time = get_current_time()
        update_landmark_from_distance()

        if beyond_reward_zone():
            enter_miss('left_reward_zone')

    elif event == 'state_timer':
        if not in_reward_zone():
            enter_miss('outside_reward_zone')
        elif hold_complete():
            goto_state('reward')
        elif zone_check_timed_out():
            enter_miss('stop_timeout')
        else:
            set_timer('state_timer', 50 * ms)

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')


def reward(event):
    if event == 'entry':
        if v.play_goal_tone:
            hw.speaker.sine(v.goal_freq_hz)
        else:
            hw.speaker.off()

        update_landmark_from_distance(force=True)

        v.reward_number += 1
        hw.reward.release()
        print('{}, reward_number'.format(v.reward_number))
        set_timer('state_timer', v.reward_post_delay)

    elif event == 'state_timer':
        goto_state('intertrial')

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        disarm_timer('state_timer')
        hw.speaker.off()


def miss(event):
    if event == 'entry':
        hw.speaker.off()
        try:
            hw.light.all_off()
        except Exception:
            pass
        set_timer('state_timer', v.miss_reset_duration)

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

    elif event == 'lick':
        v.lick_number += 1

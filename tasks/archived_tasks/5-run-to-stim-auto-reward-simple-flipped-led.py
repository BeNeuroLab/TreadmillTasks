"""Run to terminal LED zone, stop and hold, then receive automatic reward."""

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math
import random


# -------------------------------------------------------------------------
# States and Events
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
v.session_duration = 45 * minute

# Trial timing
v.intertrial_duration = 2 * second
v.trial_timeout = 15 * second
v.reward_post_delay = 0.5 * second
v.miss_reset_duration = 0.5 * second

# Reward and stopping rule
v.reward_duration = 35 * ms
v.reward_wait_time = 0.5 * second
v.stop_to_reward_timeout = 3.0 * second

# Terminal reward zone in step coordinates.
v.goal_distance_base = 60
v.goal_distance_jitter = 0.0
v.goal_distance = v.goal_distance_base
v.led_steps = 10
v.reward_zone_start_step = 8
v.nominal_target_step = 9
v.reward_boundary_step = 10
v.overshoot_margin_distance = 6
v.reward_zone_start_distance = 0
v.nominal_target_distance = 0
v.reward_boundary_distance = 0
v.reward_zone_end_distance = 0

# Distance and cue mapping.
v.current_distance = 0
v.start_freq_hz = 2000
v.zone_tone_freq_hz = 10000
v.start_led_percent = 100
v.target_led_percent = 15
v.current_step = 0
v.current_led_percent = None
v.current_freq = v.start_freq_hz

# Optional feedback and penalty features.
v.enable_teleport = False
v.play_progress_tones = False
v.play_zone_tone = True
v.use_white_noise_penalty = False
v.penalty_duration = 1.0 * second
v.penalty_noise_max_freq = 10000

# Teleportation (jump) parameters, used only when v.enable_teleport is True.
v.teleport_prob = 0.2
v.teleport_idxs = [3, 5, 7]
v.is_teleport_trial = False
v.teleport_trigger_index = 0
v.teleport_done = False
v.update_calls_in_trial = 0
v.trial_type_sequence = []

# Motion sensor parameters.
v.cpi = None
v.motion_threshold = 3
v.forward_sign = 1

# Trial tracking.
v.reward_number = 0
v.miss_number = 0
v.last_motion_time = 0
v.intertrial_start_time = 0
v.zone_entry_time = 0
v.reward_entry_time = 0
v.miss_reason = ''


# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------
def clipped_progress(progress):
    return max(0.0, min(1.0, progress))


def calculate_frequency_for_step(step):
    """Calculate frequency for a given step using a log scale."""
    octaves = math.log2(v.zone_tone_freq_hz / v.start_freq_hz)
    step_fraction = step / v.led_steps
    freq_multiplier = 2 ** (octaves * step_fraction)
    return int(v.start_freq_hz * freq_multiplier)


def led_step_from_distance(distance):
    """Map x-derived virtual distance to a discrete LED step."""
    progress = clipped_progress(distance / v.goal_distance)
    return min(v.led_steps, int(progress * v.led_steps))


def led_percent_for_step(step):
    """Map discrete LED step to center-to-side strip percent."""
    step = max(0, min(v.led_steps, step))
    step_fraction = step / v.led_steps
    percent = int(
        v.start_led_percent
        - ((v.start_led_percent - v.target_led_percent) * step_fraction)
    )
    return max(v.target_led_percent, min(v.start_led_percent, percent))


def forward_delta_distance():
    """Return forward x-axis motion since the last motion event in cm."""
    if v.cpi is None:
        raise Exception('Motion sensor CPI unavailable')

    forward_counts = v.forward_sign * hw.motionSensor.x
    if forward_counts < 0:
        forward_counts = 0

    return forward_counts / v.cpi * 2.54


def apply_feedback_step(step, play_tone=False):
    v.current_step = step
    v.current_freq = calculate_frequency_for_step(step)
    v.current_led_percent = led_percent_for_step(step)

    if play_tone and v.play_progress_tones:
        hw.speaker.sine(v.current_freq)
        print('{}, progress_frequency'.format(v.current_freq))

    try:
        hw.light.cue(v.current_led_percent)
    except Exception:
        pass

    print('{}, led_step'.format(v.current_step))
    print('{}, led_percent'.format(v.current_led_percent))


def maybe_apply_teleport():
    if not v.enable_teleport:
        return
    if not v.is_teleport_trial:
        return
    if v.teleport_done:
        return
    if v.update_calls_in_trial != v.teleport_trigger_index:
        return

    v.current_distance = v.goal_distance
    v.teleport_done = True
    print('{}, teleport_to_goal_distance'.format(round(v.current_distance, 2)))


def update_feedback_from_distance(force=False, play_tone=False, allow_teleport=True):
    """Update discrete LED feedback from x-only virtual distance."""
    if allow_teleport:
        maybe_apply_teleport()

    new_step = led_step_from_distance(v.current_distance)
    changed = new_step != v.current_step

    if force or changed:
        if changed and not force:
            v.update_calls_in_trial += 1
        apply_feedback_step(new_step, play_tone)


def configure_teleport_trial():
    v.is_teleport_trial = False
    v.teleport_trigger_index = 0

    if not v.enable_teleport:
        print('{}, teleport_trial'.format(v.is_teleport_trial))
        return

    if not v.trial_type_sequence:
        block_size = 10
        num_teleports = int(block_size * v.teleport_prob)
        if num_teleports < 0:
            num_teleports = 0
        if num_teleports > block_size:
            num_teleports = block_size

        new_block = [True] * num_teleports + [False] * (block_size - num_teleports)
        for i in range(len(new_block) - 1, 0, -1):
            j = random.randint(0, i)
            new_block[i], new_block[j] = new_block[j], new_block[i]
        v.trial_type_sequence = new_block
        print('New trial block generated: {}'.format(v.trial_type_sequence))

    v.is_teleport_trial = v.trial_type_sequence.pop(0)
    if v.is_teleport_trial:
        v.teleport_trigger_index = random.choice(v.teleport_idxs)
        print('Teleport Trial! Trigger on update #{}'.format(v.teleport_trigger_index))

    print('{}, teleport_trial'.format(v.is_teleport_trial))


def reset_trial():
    """Reset distance and compute this trial's terminal reward zone."""
    v.current_distance = 0
    v.current_step = 0
    v.current_led_percent = None
    v.current_freq = v.start_freq_hz
    v.last_motion_time = 0
    v.zone_entry_time = 0
    v.reward_entry_time = 0
    v.miss_reason = ''
    v.teleport_done = False
    v.update_calls_in_trial = 0

    jitter_fraction = 1 + random.uniform(
        -v.goal_distance_jitter,
        v.goal_distance_jitter,
    )
    v.goal_distance = v.goal_distance_base * jitter_fraction

    v.reward_zone_start_distance = (
        v.goal_distance * v.reward_zone_start_step / v.led_steps
    )
    v.nominal_target_distance = (
        v.goal_distance * v.nominal_target_step / v.led_steps
    )
    v.reward_boundary_distance = (
        v.goal_distance * v.reward_boundary_step / v.led_steps
    )
    v.reward_zone_end_distance = (
        v.reward_boundary_distance + v.overshoot_margin_distance
    )

    print('{}, new_goal_distance'.format(round(v.goal_distance, 2)))
    print('{}, reward_zone_start_distance'.format(
        round(v.reward_zone_start_distance, 2)
    ))
    print('{}, nominal_target_distance'.format(
        round(v.nominal_target_distance, 2)
    ))
    print('{}, reward_boundary_distance'.format(
        round(v.reward_boundary_distance, 2)
    ))
    print('{}, reward_zone_end_distance'.format(
        round(v.reward_zone_end_distance, 2)
    ))

    configure_teleport_trial()


def in_reward_zone():
    return (
        v.current_distance >= v.reward_zone_start_distance
        and v.current_distance <= v.reward_zone_end_distance
    )


def beyond_reward_zone():
    return v.current_distance > v.reward_zone_end_distance


def hold_complete():
    return get_current_time() - v.last_motion_time >= v.reward_wait_time


def zone_check_timed_out():
    return get_current_time() - v.zone_entry_time >= v.stop_to_reward_timeout


def enter_miss(reason):
    v.miss_number += 1
    v.miss_reason = reason
    print('{}, miss_number'.format(v.miss_number))
    print('{}, miss_reason'.format(reason))
    print('{}, miss_distance'.format(round(v.current_distance, 2)))
    goto_state('miss')


def set_reward_cues():
    try:
        hw.light.cue(led_percent_for_step(v.current_step))
    except Exception:
        pass

    if v.play_zone_tone:
        hw.speaker.sine(v.zone_tone_freq_hz)
    elif v.play_progress_tones:
        hw.speaker.sine(v.current_freq)
    else:
        hw.speaker.off()


# -------------------------------------------------------------------------
# Run Start/End
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
    print('{}, session_duration'.format(v.session_duration))
    print('{}, intertrial_duration'.format(v.intertrial_duration))
    print('{}, trial_timeout'.format(v.trial_timeout))
    print('{}, reward_wait_time'.format(v.reward_wait_time))
    print('{}, stop_to_reward_timeout'.format(v.stop_to_reward_timeout))
    print('{}, reward_post_delay'.format(v.reward_post_delay))
    print('{}, miss_reset_duration'.format(v.miss_reset_duration))
    print('{}, base_goal_distance'.format(v.goal_distance_base))
    print('{}, goal_jitter_fraction'.format(v.goal_distance_jitter))
    print('{}, led_steps'.format(v.led_steps))
    print('{}, reward_zone_start_step'.format(v.reward_zone_start_step))
    print('{}, nominal_target_step'.format(v.nominal_target_step))
    print('{}, reward_boundary_step'.format(v.reward_boundary_step))
    print('{}, overshoot_margin_distance'.format(v.overshoot_margin_distance))
    print('{}, start_led_percent'.format(v.start_led_percent))
    print('{}, target_led_percent'.format(v.target_led_percent))
    print('{}, start_frequency'.format(v.start_freq_hz))
    print('{}, zone_tone_frequency'.format(v.zone_tone_freq_hz))
    print('{}, enable_teleport'.format(v.enable_teleport))
    print('{}, play_progress_tones'.format(v.play_progress_tones))
    print('{}, play_zone_tone'.format(v.play_zone_tone))
    print('{}, use_white_noise_penalty'.format(v.use_white_noise_penalty))
    print('{}, teleport_prob'.format(v.teleport_prob))
    print('{}, teleport_idxs'.format(v.teleport_idxs))
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
    print('Session Ended')


# -------------------------------------------------------------------------
# State Machine
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
        update_feedback_from_distance(
            force=True,
            play_tone=True,
            allow_teleport=False,
        )
        if not v.play_progress_tones:
            hw.speaker.off()
        set_timer('state_timer', v.trial_timeout)

    elif event == 'motion':
        v.current_distance += forward_delta_distance()
        v.last_motion_time = get_current_time()
        update_feedback_from_distance(play_tone=True)

        if beyond_reward_zone():
            enter_miss('overshot_terminal_zone')
        elif v.current_distance >= v.reward_zone_start_distance:
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
        update_feedback_from_distance(force=True, allow_teleport=False)
        if v.play_zone_tone:
            hw.speaker.sine(v.zone_tone_freq_hz)
        print('{}, zone_entry'.format(v.zone_entry_time))
        print('{}, zone_entry_distance'.format(round(v.current_distance, 2)))
        print('{}, zone_entry_step'.format(v.current_step))
        print('{}, zone_tone_on'.format(v.play_zone_tone))
        set_timer('state_timer', 50 * ms)

    elif event == 'motion':
        v.current_distance += forward_delta_distance()
        v.last_motion_time = get_current_time()
        update_feedback_from_distance(
            play_tone=not v.play_zone_tone,
            allow_teleport=False,
        )

        if beyond_reward_zone():
            enter_miss('left_terminal_zone')

    elif event == 'state_timer':
        if not in_reward_zone():
            enter_miss('outside_terminal_zone')
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
        v.reward_entry_time = get_current_time()
        set_reward_cues()
        v.reward_number += 1
        hw.reward.release()
        print('{}, reward_number'.format(v.reward_number))
        print('{}, reward_distance'.format(round(v.current_distance, 2)))
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
        try:
            hw.light.all_off()
        except Exception:
            pass

        if v.use_white_noise_penalty:
            hw.speaker.noise(v.penalty_noise_max_freq)
            set_timer('state_timer', v.penalty_duration)
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

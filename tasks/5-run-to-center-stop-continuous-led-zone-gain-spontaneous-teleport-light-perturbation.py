"""Recording variant with teleport and full-strip light perturbations."""

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import random


# -------------------------------------------------------------------------
# States and events
# -------------------------------------------------------------------------
states = [
    'phase_router',
    'spontaneous',
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

initial_state = 'phase_router'


# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Automatic recording sequence: 5 min spontaneous before and after five
# 15 min task blocks, with four intervening 3 min spontaneous blocks.
v.session_sequence = [
    'spontaneous',
    'task',
    'spontaneous',
    'task',
    'spontaneous',
    'task',
    'spontaneous',
    'task',
    'spontaneous',
    'task',
    'spontaneous',
]
v.phase_durations = [
    5 * minute,
    15 * minute,
    3 * minute,
    15 * minute,
    3 * minute,
    15 * minute,
    3 * minute,
    15 * minute,
    3 * minute,
    15 * minute,
    5 * minute,
]

# Phase tracking.
v.current_phase_index = 0
v.current_phase = None
v.completed_phase = None
v.task_phase_number = 0
v.spontaneous_phase_number = 0

# Trial timing.
v.intertrial_duration = 1 * second
v.initiation_timeout = 5 * second
v.performance_timeout = 10 * second
v.initiation_distance_cm = 3
v.reward_cue_hold = 0.5 * second

# Reward and stopping rule.
v.reward_duration = 30 * ms
v.reward_wait_time = 250 * ms
v.stop_speed_threshold_cm_s = 5.0

# Continuous sensor polling and speed calculation.
v.sensor_update_interval = 10 * ms
v.speed_window_ms = 50

# Distance and fixed visual gain.
v.goal_distance_base = 60
v.goal_distance = v.goal_distance_base
v.current_distance = 0
v.current_visual_progress = 0.0
v.visual_gain = 1.0

# The first task phase is control-only. Later task phases use shuffled
# perturbation blocks containing 60% control, 10% light, 15% forward, and
# 15% backward trials. Perturbations trigger at 35-50% of the visual track.
v.enable_teleport = True
v.teleport_warmup_task_phases = 1
v.teleport_control_count = 12
v.light_trial_count = 2
v.teleport_forward_count = 3
v.teleport_backward_count = 3
v.teleport_trigger_min_progress = 0.35
v.teleport_trigger_max_progress = 0.50
v.teleport_magnitude_progress = 0.15
v.perturbation_trial_queue = []
v.perturbation_block_number = 0
v.perturbation_trial_type = 'control'
v.perturbation_session_phase = 'warmup'
v.teleport_direction = 0
v.teleport_trigger_progress = -1.0
v.teleport_delivered = False

# Full-strip task perturbation. Visual progress is frozen while physical
# distance and speed continue to be recorded.
v.enable_light_perturbation = True
v.light_flash_duration = 200 * ms
v.light_flash_active = False
v.light_flash_context = None
v.light_flash_start_time = 0
v.light_flash_end_time = 0
v.light_flash_delivered = False
v.light_flash_trigger_progress = -1.0
v.light_flash_frozen_progress = -1.0
v.light_flash_frozen_led_percent = 0
v.task_light_flash_count = 0

# Spontaneous flashes begin with the second spontaneous phase. Each flash is
# scheduled after a uniformly random 60-120 second interval. The cap applies
# only to spontaneous flashes.
v.enable_spontaneous_light_perturbation = True
v.spontaneous_light_warmup_phases = 1
v.spontaneous_flash_interval_min = 60 * second
v.spontaneous_flash_interval_max = 120 * second
v.spontaneous_flash_cap = 10
v.spontaneous_flash_count = 0
v.next_spontaneous_flash_interval = 0
v.next_spontaneous_flash_time = 0
v.spontaneous_phase_end_time = 0

# Continuous LED position and reward availability.
v.start_led_percent = 0
v.end_led_percent = 100
v.reward_zone_start_progress = 0.70
v.reward_zone_gain_multiplier = 1.0
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


def build_perturbation_block():
    block = []

    for i in range(max(0, int(v.teleport_control_count))):
        block.append('control')
    for i in range(max(0, int(v.light_trial_count))):
        block.append('light')
    for i in range(max(0, int(v.teleport_forward_count))):
        block.append('forward')
    for i in range(max(0, int(v.teleport_backward_count))):
        block.append('backward')

    if not block:
        block.append('control')

    return shuffle_block(block)


def configure_perturbation_trial():
    if v.task_phase_number <= v.teleport_warmup_task_phases:
        v.perturbation_trial_type = 'control'
        v.perturbation_session_phase = 'warmup'
    elif not v.enable_teleport and not v.enable_light_perturbation:
        v.perturbation_trial_type = 'control'
        v.perturbation_session_phase = 'disabled'
    else:
        v.perturbation_session_phase = 'experimental'
        if not v.perturbation_trial_queue:
            v.perturbation_trial_queue = build_perturbation_block()
            v.perturbation_block_number += 1
            print('{}, new_perturbation_block'.format(get_current_time()))
            print('{}, perturbation_block_number'.format(
                v.perturbation_block_number,
            ))
            print('{}, perturbation_block_order'.format(
                '|'.join(v.perturbation_trial_queue),
            ))

        v.perturbation_trial_type = v.perturbation_trial_queue.pop(0)

    if (
        v.perturbation_trial_type == 'forward'
        and v.enable_teleport
    ):
        v.teleport_direction = 1
    elif (
        v.perturbation_trial_type == 'backward'
        and v.enable_teleport
    ):
        v.teleport_direction = -1
    elif (
        v.perturbation_trial_type == 'light'
        and v.enable_light_perturbation
    ):
        v.teleport_direction = 0
    else:
        v.perturbation_trial_type = 'control'
        v.teleport_direction = 0

    if v.teleport_direction or v.perturbation_trial_type == 'light':
        trigger_progress = random.uniform(
            v.teleport_trigger_min_progress,
            v.teleport_trigger_max_progress,
        )
        v.teleport_trigger_progress = trigger_progress
        v.light_flash_trigger_progress = (
            trigger_progress
            if v.perturbation_trial_type == 'light'
            else -1.0
        )
    else:
        v.teleport_trigger_progress = -1.0
        v.light_flash_trigger_progress = -1.0

    v.teleport_delivered = False
    v.light_flash_delivered = False


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
    return v.current_visual_progress


def add_visual_progress(raw_progress):
    """Advance the cursor, applying the configured reward-zone multiplier."""
    if raw_progress <= 0:
        return

    if v.current_visual_progress < v.reward_zone_start_progress:
        progress_to_zone = (
            v.reward_zone_start_progress - v.current_visual_progress
        )
        progress_before_zone = min(raw_progress, progress_to_zone)
        v.current_visual_progress += progress_before_zone
        raw_progress -= progress_before_zone

    if raw_progress > 0:
        v.current_visual_progress += (
            raw_progress * v.reward_zone_gain_multiplier
        )


def deliver_teleport():
    preteleport_progress = v.current_visual_progress
    signed_magnitude = (
        v.teleport_direction * v.teleport_magnitude_progress
    )
    v.current_visual_progress += signed_magnitude
    v.teleport_delivered = True
    teleport_time = get_current_time()

    print('{}, teleport_delivered'.format(teleport_time))
    print('{}, teleport_timestamp'.format(teleport_time))
    print('{}, teleport_direction'.format(v.perturbation_trial_type))
    print('{}, teleport_signed_magnitude_progress'.format(
        round(signed_magnitude, 4),
    ))
    print('{}, teleport_trigger_progress'.format(
        round(v.teleport_trigger_progress, 4),
    ))
    print('{}, actual_preteleport_progress'.format(
        round(preteleport_progress, 4),
    ))
    print('{}, actual_postteleport_progress'.format(
        round(v.current_visual_progress, 4),
    ))
    print('{}, teleport_physical_distance_cm'.format(
        round(v.current_distance, 3),
    ))
    print('{}, speed_at_teleport_cm_s'.format(
        round(v.rolling_speed_cm_s, 3),
    ))


def show_full_strip():
    try:
        hw.light.send_int(202)
        return True
    except Exception as error:
        print('{}, light_flash_command_failed'.format(get_current_time()))
        print('{}, light_flash_command_error'.format(repr(error)))
        return False


def start_task_light_flash():
    v.light_flash_active = True
    v.light_flash_context = 'task'
    v.light_flash_delivered = True
    v.light_flash_frozen_progress = v.current_visual_progress
    v.light_flash_frozen_led_percent = v.current_led_percent
    v.task_light_flash_count += 1
    flash_time = get_current_time()
    v.light_flash_start_time = flash_time
    v.light_flash_end_time = flash_time + v.light_flash_duration

    command_sent = show_full_strip()
    print('{}, task_light_flash_on'.format(flash_time))
    print('{}, task_light_flash_count'.format(v.task_light_flash_count))
    print('{}, task_light_flash_command_sent'.format(command_sent))
    print('{}, task_light_flash_trigger_progress'.format(
        round(v.light_flash_trigger_progress, 4),
    ))
    print('{}, task_light_flash_frozen_progress'.format(
        round(v.light_flash_frozen_progress, 4),
    ))
    print('{}, task_light_flash_frozen_led_percent'.format(
        v.light_flash_frozen_led_percent,
    ))
    print('{}, task_light_flash_physical_distance_cm'.format(
        round(v.current_distance, 3),
    ))
    print('{}, speed_at_task_light_flash_cm_s'.format(
        round(v.rolling_speed_cm_s, 3),
    ))


def finish_task_light_flash():
    flash_time = get_current_time()
    v.light_flash_active = False
    v.light_flash_context = None
    set_led_baseline()
    set_led_state(v.light_flash_frozen_led_percent)
    print('{}, task_light_flash_off'.format(flash_time))
    print('{}, task_light_flash_actual_duration_ms'.format(
        flash_time - v.light_flash_start_time,
    ))
    print('{}, task_light_flash_restored_progress'.format(
        round(v.current_visual_progress, 4),
    ))
    print('{}, task_light_flash_restored_led_percent'.format(
        v.light_flash_frozen_led_percent,
    ))
    print('{}, task_light_flash_end_physical_distance_cm'.format(
        round(v.current_distance, 3),
    ))


def start_spontaneous_light_flash():
    flash_time = get_current_time()
    v.light_flash_start_time = flash_time
    v.light_flash_end_time = flash_time + v.light_flash_duration
    v.light_flash_active = True
    v.light_flash_context = 'spontaneous'
    v.spontaneous_flash_count += 1

    command_sent = show_full_strip()
    print('{}, spontaneous_light_flash_on'.format(flash_time))
    print('{}, spontaneous_light_flash_count'.format(
        v.spontaneous_flash_count,
    ))
    print('{}, spontaneous_light_flash_command_sent'.format(command_sent))
    print('{}, spontaneous_light_flash_phase_number'.format(
        v.spontaneous_phase_number,
    ))


def finish_spontaneous_light_flash():
    flash_time = get_current_time()
    v.light_flash_active = False
    v.light_flash_context = None
    try:
        hw.light.all_off()
    except Exception:
        pass
    print('{}, spontaneous_light_flash_off'.format(flash_time))
    print('{}, spontaneous_light_flash_actual_duration_ms'.format(
        flash_time - v.light_flash_start_time,
    ))


def cancel_light_flash(reason, restore_mode):
    if not v.light_flash_active:
        return

    context = v.light_flash_context
    v.light_flash_active = False
    v.light_flash_context = None
    print('{}, light_flash_cancelled'.format(get_current_time()))
    print('{}, light_flash_cancel_context'.format(context))
    print('{}, light_flash_cancel_reason'.format(reason))
    print('{}, light_flash_cancel_elapsed_ms'.format(
        get_current_time() - v.light_flash_start_time,
    ))

    if restore_mode == 'task':
        set_led_baseline()
        set_led_state(v.light_flash_frozen_led_percent)
    elif restore_mode == 'baseline':
        set_led_baseline()
    else:
        try:
            hw.light.all_off()
        except Exception:
            pass


def advance_visual_progress(distance_cm):
    if v.goal_distance <= 0:
        v.current_visual_progress = 1.0
        return

    if v.light_flash_active and v.light_flash_context == 'task':
        return

    raw_progress = distance_cm * v.visual_gain / v.goal_distance

    perturbation_pending = (
        (
            v.enable_teleport
            and v.teleport_direction != 0
            and not v.teleport_delivered
        )
        or (
            v.enable_light_perturbation
            and v.perturbation_trial_type == 'light'
            and not v.light_flash_delivered
        )
    )
    crosses_trigger = (
        perturbation_pending
        and v.current_visual_progress < v.teleport_trigger_progress
        and (
            v.current_visual_progress + raw_progress
            >= v.teleport_trigger_progress
        )
    )

    if crosses_trigger:
        progress_to_trigger = (
            v.teleport_trigger_progress - v.current_visual_progress
        )
        add_visual_progress(progress_to_trigger)
        raw_progress -= progress_to_trigger
        if v.perturbation_trial_type == 'light':
            start_task_light_flash()
            return
        else:
            deliver_teleport()

    add_visual_progress(raw_progress)


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
    if v.light_flash_active:
        return
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
    v.current_visual_progress = 0.0
    v.current_led_percent = 0
    v.target_reached_time = 0
    v.trial_start_time = 0
    v.initiation_time = 0
    v.trial_phase = 'initiation'
    v.light_flash_active = False
    v.light_flash_context = None
    v.light_flash_frozen_progress = -1.0
    v.light_flash_frozen_led_percent = 0
    configure_perturbation_trial()


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


def schedule_next_spontaneous_flash():
    v.next_spontaneous_flash_time = 0
    if not v.enable_spontaneous_light_perturbation:
        return
    if v.spontaneous_phase_number <= v.spontaneous_light_warmup_phases:
        return
    if v.spontaneous_flash_count >= v.spontaneous_flash_cap:
        return

    v.next_spontaneous_flash_interval = random.randint(
        int(v.spontaneous_flash_interval_min),
        int(v.spontaneous_flash_interval_max),
    )
    v.next_spontaneous_flash_time = (
        get_current_time() + v.next_spontaneous_flash_interval
    )
    print('{}, spontaneous_light_flash_scheduled'.format(
        get_current_time(),
    ))
    print('{}, spontaneous_light_flash_interval_ms'.format(
        v.next_spontaneous_flash_interval,
    ))


def schedule_spontaneous_state_timer():
    now = get_current_time()
    next_deadline = v.spontaneous_phase_end_time

    if v.light_flash_active and v.light_flash_context == 'spontaneous':
        next_deadline = min(next_deadline, v.light_flash_end_time)
    elif v.next_spontaneous_flash_time > 0:
        next_deadline = min(
            next_deadline,
            v.next_spontaneous_flash_time,
        )

    set_timer('state_timer', max(1, next_deadline - now))


VALID_PHASES = ('spontaneous', 'task')


def validate_session_sequence():
    if not isinstance(v.session_sequence, (list, tuple)):
        raise ValueError(
            'v.session_sequence must be a list or tuple of phase names.'
        )
    if not v.session_sequence:
        raise ValueError(
            'v.session_sequence must contain at least one phase.'
        )
    if not isinstance(v.phase_durations, (list, tuple)):
        raise ValueError(
            'v.phase_durations must be a list or tuple of durations.'
        )
    if len(v.phase_durations) != len(v.session_sequence):
        raise ValueError(
            'v.phase_durations must match v.session_sequence length.'
        )
    if any(duration <= 0 for duration in v.phase_durations):
        raise ValueError('All recording phase durations must be positive.')

    normalized_sequence = []
    invalid_phases = []
    for phase in v.session_sequence:
        if not isinstance(phase, str):
            invalid_phases.append(repr(phase))
            continue
        normalized_phase = phase.lower()
        if normalized_phase not in VALID_PHASES:
            invalid_phases.append(repr(phase))
            continue
        normalized_sequence.append(normalized_phase)

    if invalid_phases:
        raise ValueError(
            'Invalid phase names in v.session_sequence: {}'.format(
                ', '.join(invalid_phases),
            )
        )

    v.session_sequence = normalized_sequence


def current_phase_name():
    return v.session_sequence[v.current_phase_index]


def current_phase_duration():
    return v.phase_durations[v.current_phase_index]


def start_current_phase():
    phase = current_phase_name()
    duration = current_phase_duration()
    v.current_phase = phase

    print('{}, phase_index'.format(v.current_phase_index + 1))
    print('{}, phase_duration_ms'.format(duration))
    if phase == 'task':
        v.task_phase_number += 1
        print('{}, task_phase_number'.format(v.task_phase_number))
        print('{}, task_phase_start'.format(get_current_time()))
        set_timer('session_timer', duration)
        goto_state('intertrial')
    else:
        v.spontaneous_phase_number += 1
        print('{}, spontaneous_phase_number'.format(
            v.spontaneous_phase_number,
        ))
        goto_state('spontaneous')


def advance_phase():
    disarm_timer('session_timer')
    v.completed_phase = current_phase_name()
    print('{}, completed_phase'.format(v.completed_phase))
    v.current_phase_index += 1

    if v.current_phase_index >= len(v.session_sequence):
        print('{}, recording_sequence_complete'.format(get_current_time()))
        stop_framework()
        return

    print('{}, next_phase'.format(current_phase_name()))
    start_current_phase()


# -------------------------------------------------------------------------
# Run start/end
# -------------------------------------------------------------------------
def run_start():
    validate_session_sequence()
    v.current_phase_index = 0
    v.current_phase = None
    v.completed_phase = None
    v.task_phase_number = 0
    v.spontaneous_phase_number = 0
    v.perturbation_trial_queue = []
    v.perturbation_block_number = 0
    v.task_light_flash_count = 0
    v.spontaneous_flash_count = 0
    v.next_spontaneous_flash_interval = 0
    v.next_spontaneous_flash_time = 0
    v.spontaneous_phase_end_time = 0
    v.light_flash_active = False
    v.light_flash_context = None
    v.light_flash_start_time = 0
    v.light_flash_end_time = 0

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
    if v.visual_gain <= 0:
        raise Exception('visual_gain must be positive')
    if v.initiation_distance_cm <= 0:
        raise Exception('initiation_distance_cm must be positive')
    if v.initiation_timeout <= 0 or v.performance_timeout <= 0:
        raise Exception('Initiation and performance timeouts must be positive')
    if not 0 <= v.start_led_percent < v.end_led_percent <= 100:
        raise Exception('Continuous LED range must be within 0 to 100')
    if min(
        v.teleport_control_count,
        v.light_trial_count,
        v.teleport_forward_count,
        v.teleport_backward_count,
    ) < 0:
        raise Exception('Perturbation block counts cannot be negative')
    if sum((
        v.teleport_control_count,
        v.light_trial_count,
        v.teleport_forward_count,
        v.teleport_backward_count,
    )) <= 0:
        raise Exception('Perturbation block must contain at least one trial')
    if v.teleport_warmup_task_phases < 0:
        raise Exception('teleport_warmup_task_phases cannot be negative')
    if v.teleport_magnitude_progress <= 0:
        raise Exception('teleport_magnitude_progress must be positive')
    if v.light_flash_duration <= 0:
        raise Exception('light_flash_duration must be positive')
    if v.spontaneous_light_warmup_phases < 0:
        raise Exception('spontaneous_light_warmup_phases cannot be negative')
    if v.spontaneous_flash_interval_min <= 0:
        raise Exception(
            'spontaneous_flash_interval_min must be positive'
        )
    if (
        v.spontaneous_flash_interval_max
        < v.spontaneous_flash_interval_min
    ):
        raise Exception(
            'spontaneous flash maximum interval must be at least minimum'
        )
    if v.spontaneous_flash_cap < 0:
        raise Exception('spontaneous_flash_cap cannot be negative')
    if not (
        0 < v.teleport_trigger_min_progress
        <= v.teleport_trigger_max_progress
        < v.reward_zone_start_progress
    ):
        raise Exception('Teleport triggers must be before the reward zone')
    if (
        v.teleport_trigger_min_progress
        - v.teleport_magnitude_progress < 0
    ):
        raise Exception('Backward teleport would move before track start')
    if (
        v.teleport_trigger_max_progress
        + v.teleport_magnitude_progress
        >= v.reward_zone_start_progress
    ):
        raise Exception('Forward teleport must finish before the reward zone')

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
    print('{}, session_sequence'.format(v.session_sequence))
    print('{}, phase_durations_ms'.format(v.phase_durations))
    print('{}, total_recording_duration_ms'.format(
        sum(v.phase_durations),
    ))
    print('{}, visual_gain'.format(v.visual_gain))
    print('{}, enable_teleport'.format(v.enable_teleport))
    print('{}, teleport_warmup_task_phases'.format(
        v.teleport_warmup_task_phases,
    ))
    print('{}, teleport_control_count'.format(v.teleport_control_count))
    print('{}, light_trial_count'.format(v.light_trial_count))
    print('{}, teleport_forward_count'.format(v.teleport_forward_count))
    print('{}, teleport_backward_count'.format(v.teleport_backward_count))
    print('{}, teleport_trigger_min_progress'.format(
        v.teleport_trigger_min_progress,
    ))
    print('{}, teleport_trigger_max_progress'.format(
        v.teleport_trigger_max_progress,
    ))
    print('{}, teleport_magnitude_progress'.format(
        v.teleport_magnitude_progress,
    ))
    print('{}, enable_light_perturbation'.format(
        v.enable_light_perturbation,
    ))
    print('{}, light_flash_duration_ms'.format(v.light_flash_duration))
    print('{}, enable_spontaneous_light_perturbation'.format(
        v.enable_spontaneous_light_perturbation,
    ))
    print('{}, spontaneous_light_warmup_phases'.format(
        v.spontaneous_light_warmup_phases,
    ))
    print('{}, spontaneous_flash_interval_min_ms'.format(
        v.spontaneous_flash_interval_min,
    ))
    print('{}, spontaneous_flash_interval_max_ms'.format(
        v.spontaneous_flash_interval_max,
    ))
    print('{}, spontaneous_flash_cap'.format(v.spontaneous_flash_cap))
    print('{}, before_camera_trigger'.format(get_current_time()))

    hw.cameraTrigger.start()
    # Phase-specific timers start after the camera trigger.


def run_end():
    cancel_light_flash('run_end', 'off')
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
    print('{}, total_task_light_flashes'.format(v.task_light_flash_count))
    print('{}, total_spontaneous_light_flashes'.format(
        v.spontaneous_flash_count,
    ))
    print('Session Ended')


# -------------------------------------------------------------------------
# Automatic phase routing
# -------------------------------------------------------------------------
def phase_router(event):
    if event == 'entry':
        print('{}, recording_sequence_start'.format(get_current_time()))
        set_timer('state_timer', 1 * ms)

    elif event == 'state_timer':
        start_current_phase()

    elif event == 'exit':
        disarm_timer('state_timer')


def spontaneous(event):
    if event == 'entry':
        hw.speaker.off()
        disarm_timer('tone_off_timer')
        try:
            hw.light.all_off()
        except Exception:
            pass
        print('{}, spontaneous_phase_start'.format(get_current_time()))
        v.spontaneous_phase_end_time = (
            get_current_time() + current_phase_duration()
        )
        v.next_spontaneous_flash_time = 0
        if (
            v.enable_spontaneous_light_perturbation
            and v.spontaneous_phase_number
            > v.spontaneous_light_warmup_phases
        ):
            schedule_next_spontaneous_flash()
        schedule_spontaneous_state_timer()

    elif event == 'state_timer':
        now = get_current_time()
        if now >= v.spontaneous_phase_end_time:
            advance_phase()
        elif (
            v.light_flash_active
            and v.light_flash_context == 'spontaneous'
            and now >= v.light_flash_end_time
        ):
            finish_spontaneous_light_flash()
            schedule_next_spontaneous_flash()
            schedule_spontaneous_state_timer()
        elif (
            v.next_spontaneous_flash_time > 0
            and now >= v.next_spontaneous_flash_time
        ):
            v.next_spontaneous_flash_time = 0
            start_spontaneous_light_flash()
            schedule_spontaneous_state_timer()
        else:
            schedule_spontaneous_state_timer()

    elif event == 'exit':
        disarm_timer('state_timer')
        cancel_light_flash('spontaneous_phase_exit', 'off')


# -------------------------------------------------------------------------
# Task states
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
        print('{}, visual_gain'.format(v.visual_gain))
        print('{}, perturbation_session_phase'.format(
            v.perturbation_session_phase,
        ))
        print('{}, perturbation_trial_type'.format(
            v.perturbation_trial_type,
        ))
        print('{}, planned_teleport_direction'.format(
            v.teleport_direction,
        ))
        print('{}, planned_teleport_magnitude_progress'.format(
            v.teleport_magnitude_progress
            if v.teleport_direction else 0.0,
        ))
        print('{}, planned_teleport_trigger_progress'.format(
            round(v.teleport_trigger_progress, 4),
        ))
        print('{}, planned_light_flash_duration_ms'.format(
            v.light_flash_duration
            if v.perturbation_trial_type == 'light'
            else 0,
        ))
        print('{}, planned_light_flash_trigger_progress'.format(
            round(v.light_flash_trigger_progress, 4),
        ))
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
        distance_increment = poll_motion_sensor()
        v.current_distance += distance_increment
        advance_visual_progress(distance_increment)
        if (
            v.light_flash_active
            and v.light_flash_context == 'task'
            and get_current_time() >= v.light_flash_end_time
        ):
            finish_task_light_flash()

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
        cancel_light_flash('trial_exit', 'baseline')


def target_wait(event):
    if event == 'entry':
        schedule_sensor_update()

    elif event == 'sensor_update':
        distance_increment = poll_motion_sensor()
        v.current_distance += distance_increment
        advance_visual_progress(distance_increment)

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
        print('{}, task_phase_complete'.format(get_current_time()))
        advance_phase()
        return True

    elif event == 'tone_off_timer':
        hw.speaker.off()

    elif event == 'lick':
        v.lick_number += 1

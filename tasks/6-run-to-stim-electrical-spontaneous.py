"""Run-to-stim task (spontaneous + penalty + auto-delivery) that also triggers
and tracks electrical stimulation.

Based on `5-run-to-stim-with-priming-penalty-spontaneous.py`. On top of that
task it:
  * sends a stimulation command code to the cl_stim trigger server
    (`run_stimulation.py`) at a trial-randomized timing condition;
  * tracks stimulation by logging marker codes echoed back by the trigger
    server (run it with `--notify-pycontrol` so it sends stim_on/stim_off).

The stimulation *parameters and duration* live in cl_stim's `config.toml`
(experiment profile + command map). This task only chooses which command code
to fire and when; the trigger server enforces the train duration.

Command/marker codes must match cl_stim `config.toml`:
  [experiments.<exp>.commands.<code>]  -> v.stim_command_codes (what we SEND)
  [pycontrol_events.codes]             -> v.code_stim_*       (what we RECEIVE)
"""

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math
import random

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'phase_router',
    'spontaneous',
    'setup',
    'intertrial',
    'trial',
    'reward',          # Goal reached; wait for stillness to enter priming
    'priming',         # LED blinks; lick here to obtain reward
    'penalty',         # White noise + lights off after miss
    'post_reward',     # Keep stimulus after reward
    'stopped'
]

events = [
    'session_timer',
    'state_timer',     # General timer for state checks/windows
    'blink_timer',     # LED blink timer in priming
    'stim_delay_timer', # STIM: delayed trigger after first motion
    'motion',          # Motion events from sensor
    'lick',
    'stop_button',
    'cursor_update',   # STIM: marker received from the cl_stim trigger server
]

initial_state = 'phase_router'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session parameters
v.session_duration = 30 * minute
v.spontaneous_duration = 5 * minute
v.session_sequence = ['spontaneous', 'task', 'spontaneous', 'task','spontaneous']

# Manual transition trigger
v.start_next_phase_now = False

# Trial parameters
v.intertrial_duration = 2 * second
v.trial_timeout = 15 * second         # Max time to reach target distance
v.motion_wait_time = 0.5 * second     # Time without motion before trial can start
v.reward_duration = 35 * ms
v.target_present_duration = 1 * second  # Duration to play goal frequency after reward

# Stop/priming parameters
v.priming_wait_time = 0.5 * second      # Required stillness before entering priming
v.priming_window = 3.0 * second         # Time in priming to obtain reward by lick
v.priming_blink_period = 250 * ms       # LED blink period during priming
v.stop_to_prime_timeout = 5.0 * second  # If staying in reward without stopping -> penalty

# Penalty parameters
v.penalty_duration = 1.0 * second
v.penalty_noise_max_freq = 10000        # Upper freq for white noise

# Distance and frequency mapping
v.goal_distance_base = 60       # Base distance units to reach goal
v.goal_distance_jitter = 0.20   # ±20% randomization per trial
v.goal_distance = v.goal_distance_base
v.current_distance = 0          # Accumulated distance traveled
v.start_freq_hz = 2000          # Starting frequency (Hz)
v.goal_freq_hz = 10000          # Goal frequency (Hz)

# Discrete frequency steps (speaker)
v.num_steps = 10                # Number of discrete frequency steps (like semitones)
v.current_step = 0              # Current frequency step
v.current_freq = v.start_freq_hz

# Teleportation (jump) parameters
v.teleport_prob = 0.2           # 20% of trials are teleport trials
v.teleport_idxs = [3, 5, 7]     # Step-change indices that can trigger teleport
v.is_teleport_trial = False
v.teleport_trigger_index = 0    # Which step triggers the teleport
v.update_calls_in_trial = 0     # Count of step changes in current trial
v.trial_type_sequence = []      # List to manage block randomization

# Motion sensor parameters
v.cpi = 100                     # Counts per inch (will be updated from sensor)
v.motion_threshold = 3          # Motion event threshold

# Trial tracking
v.reward_number = 0
v.last_motion_time = 0          # Track when last motion occurred
v.motion_detected = False       # Flag for motion during wait period
v.intertrial_start_time = 0
v.reward_entry_time = 0         # Track time of entering reward state
v.current_phase_index = 0
v.current_phase = None
v.completed_phase = None
v.next_phase = None
v.trial_number = 0

# Priming reward during setup
v.priming_reward_cooldown = 10 * second  # Min time between priming rewards
v.last_priming_reward_time = 0           # Last time a priming reward was given

# -------------------------------------------------------------------------
# STIM: electrical stimulation control + tracking
# -------------------------------------------------------------------------
# Command codes SENT to the trigger server. Must match cl_stim
# [experiments.m2_timing.commands]: 1=sham, 2=m2_stim.
v.stim_enabled = True
v.stim_command_codes = [1, 2]
v.stim_timing_conditions = ['cue_start', 'first_motion_delay', 'cue_position']
v.stim_repeats_per_condition = 4
v.stim_motion_delay = 100 * ms
v.stim_cue_step = 5
v.stim_trial_queue = []
v.stim_block_number = 0
v.current_stim_timing = 'none'
v.current_stim_code = 0
v.current_stim_condition = 'none'
v.stim_sent_this_trial = False
v.first_motion_seen = False

# Only fire stimulation during 'task' phases.
v.stim_in_task_only = True

# Marker codes RECEIVED back from the trigger server (run it with
# --notify-pycontrol). Must match cl_stim/config.toml [pycontrol_events.codes].
v.code_stim_on = 101
v.code_stim_off = 102
v.code_stim_pulse = 103
v.code_session_start = 110
v.code_session_end = 111
v.code_session_marker_to_stim = 0

# Tracking counters
v.stim_trigger_count = 0        # Times we asked the server to stimulate
v.marker_count = 0              # Markers received back
v.stim_on_count = 0
v.stim_off_count = 0
v.stim_pulse_count = 0
v.unknown_marker_count = 0
v.stim_active = False

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------
def calculate_frequency_for_step(step):
    """Calculate frequency for a given step using log scale (octaves)"""
    octaves = math.log2(v.goal_freq_hz / v.start_freq_hz)
    step_fraction = step / v.num_steps
    freq_multiplier = 2 ** (octaves * step_fraction)
    return int(v.start_freq_hz * freq_multiplier)

def led_percent_from_progress(progress: float) -> int:
    """Map progress [0..1] to LED strip percent for bilateral (side -> center)."""
    p = int(100 * max(0.0, min(1.0, progress)))
    return min(100, p)

def set_led_blinking(enabled: bool):
    try:
        if enabled:
            # Background stays red; blink will toggle the target LED blue/red
            hw.light.all_red()
            v._blink_on = False
            set_timer('blink_timer', v.priming_blink_period, True)
        else:
            disarm_timer('blink_timer')
            try:
                hw.light.all_red()
            except Exception:
                pass
    except Exception:
        pass

def toggle_led():
    """Blink by alternating the target LED between blue (cue) and red background only."""
    try:
        if getattr(v, '_blink_on', False):
            # Turn target back to red background only
            hw.light.all_red()
            v._blink_on = False
        else:
            # Show target LED in blue while others remain red
            hw.light.cue(v.target_led_percent)
            v._blink_on = True
    except Exception:
        pass

# -------------------------------------------------------------------------
# STIM helpers
# -------------------------------------------------------------------------
def send_to_stim(code):
    """Send a 2-byte code to the cl_stim trigger server over the bci_link UART."""
    if hasattr(hw, 'bci_link'):
        hw.bci_link.send_int_to_bci(code)
        return True
    print('{}, missing_bci_link'.format(get_current_time()))
    return False

def stim_condition_name(code):
    if code == 1:
        return 'sham'
    if code == 2:
        return 'm2_stim'
    return 'unknown'

def stim_delay_ms():
    return int(v.stim_motion_delay / ms)

def teleport_type_name():
    if v.is_teleport_trial:
        return 'teleport'
    return 'normal'

def build_stim_trial_block():
    block = []
    repeats = int(v.stim_repeats_per_condition)
    if repeats < 1:
        print('Warning: stim_repeats_per_condition < 1, using 1')
        repeats = 1

    if not v.stim_command_codes:
        print('Warning: empty stim_command_codes; using sham command 1')
        v.stim_command_codes = [1]

    if not v.stim_timing_conditions:
        print('Warning: empty stim_timing_conditions; using cue_start')
        v.stim_timing_conditions = ['cue_start']

    for _ in range(repeats):
        for timing in v.stim_timing_conditions:
            for code in v.stim_command_codes:
                block.append([timing, code])

    for i in range(len(block) - 1, 0, -1):
        j = random.randint(0, i)
        block[i], block[j] = block[j], block[i]
    return block

def choose_stim_trial_condition():
    v.stim_sent_this_trial = False
    v.first_motion_seen = False
    disarm_timer('stim_delay_timer')

    if not v.stim_enabled:
        v.current_stim_timing = 'disabled'
        v.current_stim_code = 0
        v.current_stim_condition = 'disabled'
        return

    if not v.stim_trial_queue:
        v.stim_trial_queue = build_stim_trial_block()
        v.stim_block_number += 1
        print(
            '{}, new_stim_block block={} order={}'.format(
                get_current_time(), v.stim_block_number, v.stim_trial_queue
            )
        )

    assignment = v.stim_trial_queue.pop(0)
    v.current_stim_timing = assignment[0]
    v.current_stim_code = assignment[1]
    v.current_stim_condition = stim_condition_name(v.current_stim_code)
    v.trial_number += 1
    print(
        '{}, stim_trial_assigned trial={} block={} timing={} code={} condition={} cue_step={} delay_ms={} teleport_type={}'.format(
            get_current_time(),
            v.trial_number,
            v.stim_block_number,
            v.current_stim_timing,
            v.current_stim_code,
            v.current_stim_condition,
            v.stim_cue_step,
            stim_delay_ms(),
            teleport_type_name()
        )
    )

def trigger_stim(reason):
    """Send this trial's assigned stimulation command to the trigger server."""
    if not v.stim_enabled:
        return
    if v.stim_in_task_only and v.current_phase != 'task':
        return
    if v.stim_sent_this_trial:
        return

    v.stim_sent_this_trial = True
    disarm_timer('stim_delay_timer')

    if send_to_stim(v.current_stim_code):
        v.stim_trigger_count += 1
        print(
            '{}, stim_trial trial={} block={} timing={} code={} condition={} reason={} cue_step={} delay_ms={} teleport_type={} trigger_count={}'.format(
                get_current_time(),
                v.trial_number,
                v.stim_block_number,
                v.current_stim_timing,
                v.current_stim_code,
                v.current_stim_condition,
                reason,
                v.stim_cue_step,
                stim_delay_ms(),
                teleport_type_name(),
                v.stim_trigger_count
            )
        )
    else:
        print(
            '{}, stim_trial_send_failed trial={} timing={} code={} condition={} reason={} teleport_type={}'.format(
                get_current_time(),
                v.trial_number,
                v.current_stim_timing,
                v.current_stim_code,
                v.current_stim_condition,
                reason,
                teleport_type_name()
            )
        )

def maybe_trigger_cue_position_stim():
    if v.current_stim_timing != 'cue_position':
        return
    if v.current_step >= v.stim_cue_step:
        trigger_stim('cue_position')

def marker_name(code):
    if code == v.code_stim_on:
        return 'stim_on'
    if code == v.code_stim_off:
        return 'stim_off'
    if code == v.code_stim_pulse:
        return 'stim_pulse'
    if code == v.code_session_start:
        return 'session_start'
    if code == v.code_session_end:
        return 'session_end'
    return 'unknown'

def log_marker(code):
    """Record a stimulation marker echoed back by the trigger server."""
    name = marker_name(code)
    v.marker_count += 1
    if name == 'stim_on':
        v.stim_on_count += 1
        v.stim_active = True
    elif name == 'stim_off':
        v.stim_off_count += 1
        v.stim_active = False
    elif name == 'stim_pulse':
        v.stim_pulse_count += 1
        v.stim_active = False
    elif name == 'unknown':
        v.unknown_marker_count += 1
    print(
        '{}, external_stim_marker code={} name={} count={} active={}'.format(
            get_current_time(), code, name, v.marker_count, v.stim_active
        )
    )

def print_stim_summary():
    print(
        '{}, external_stim_summary triggers={} markers={} stim_on={} '
        'stim_off={} stim_pulse={} unknown={}'.format(
            get_current_time(), v.stim_trigger_count, v.marker_count,
            v.stim_on_count, v.stim_off_count, v.stim_pulse_count,
            v.unknown_marker_count
        )
    )

VALID_PHASES = ('spontaneous', 'task')

def validate_session_sequence():
    if not isinstance(v.session_sequence, (list, tuple)):
        raise ValueError('v.session_sequence must be a list or tuple of phase names.')
    if not v.session_sequence:
        raise ValueError('v.session_sequence must contain at least one phase.')

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
            'Invalid phase names in v.session_sequence: {}'.format(', '.join(invalid_phases))
        )

    v.session_sequence = normalized_sequence

def current_phase_name():
    return v.session_sequence[v.current_phase_index]

def start_current_phase():
    phase = current_phase_name()
    v.current_phase = phase
    v.next_phase = None

    if phase == 'task':
        set_timer('session_timer', v.session_duration)
        print(
            'Starting Task Phase {}/{} ({}s)'.format(
                v.current_phase_index + 1,
                len(v.session_sequence),
                v.session_duration / second
            )
        )
        goto_state('intertrial')
    else:
        goto_state('spontaneous')

def advance_phase():
    v.completed_phase = current_phase_name()
    v.current_phase_index += 1

    if v.current_phase_index >= len(v.session_sequence):
        print('Completed final {} phase. Stopping framework.'.format(v.completed_phase))
        if v.completed_phase != 'task':
            print('{}, total_rewards'.format(v.reward_number))
        stop_framework()
        return

    v.next_phase = current_phase_name()
    print('Completed {} phase. Next phase: {}.'.format(v.completed_phase, v.next_phase))
    goto_state('setup')

def update_feedback_from_distance():
    """Update speaker and LED feedback based on current distance."""
    # Teleportation check: jump to goal on specific step
    if v.is_teleport_trial and (v.update_calls_in_trial == v.teleport_trigger_index):
        v.current_distance = v.goal_distance
        print('Teleporting to goal!')

    # Progress in [0,1]
    progress = min(v.current_distance / v.goal_distance, 1.0)

    # Speaker and LED: discrete steps (synchronized)
    new_step = int(progress * v.num_steps)
    if new_step != v.current_step:
        v.current_step = new_step
        v.update_calls_in_trial += 1
        v.current_freq = calculate_frequency_for_step(v.current_step)
        hw.speaker.sine(v.current_freq)
        print('{}, distance'.format(v.current_distance))
        print('{}, frequency'.format(v.current_freq))

        # LED strip: bilateral side -> center (update only on step change)
        try:
            led_p = led_percent_from_progress(progress)
            hw.light.cue(led_p)
            print('{}, led_percent'.format(led_p))
        except Exception:
            pass

        # Fire cue-position stimulation only after the visible cue update.
        maybe_trigger_cue_position_stim()

    # Check if we've reached the goal (complete distance)
    if v.current_distance >= v.goal_distance:
        print('{}, target_reached'.format(v.goal_freq_hz))
        goto_state('reward')

def reset_trial():
    """Reset distance/frequency and apply random jitter to goal distance."""
    v.current_distance = 0
    v.current_step = 0
    v.current_freq = v.start_freq_hz
    v.motion_detected = False
    v.update_calls_in_trial = 0

    # Apply ±jitter% (uniform)
    jitter_fraction = 1 + random.uniform(-v.goal_distance_jitter, v.goal_distance_jitter)
    v.goal_distance = v.goal_distance_base * jitter_fraction
    print('{}, new_goal_distance'.format(round(v.goal_distance, 2)))

    # Determine trial type (Teleport vs Normal) using block randomization
    if not v.trial_type_sequence:
        block_size = 10
        num_teleports = int(block_size * v.teleport_prob)
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
    else:
        print('Normal Trial')

    choose_stim_trial_condition()

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    validate_session_sequence()
    v.current_phase_index = 0
    v.current_phase = None
    v.completed_phase = None
    v.next_phase = current_phase_name()
    v.start_next_phase_now = False

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

    # STIM: open the link to the cl_stim trigger server and mark session start.
    if hasattr(hw, 'bci_link'):
        hw.bci_link.start()
        print('{}, bci_link_started'.format(get_current_time()))
        send_to_stim(v.code_session_marker_to_stim)
        print(
            '{}, sent_session_marker_to_stim code={} phase=start'.format(
                get_current_time(), v.code_session_marker_to_stim
            )
        )
    else:
        print('{}, missing_bci_link'.format(get_current_time()))

    print('{}, CPI'.format(v.cpi))
    print('{}, motion_threshold'.format(v.motion_threshold))
    print('{}, motion_wait_time'.format(v.motion_wait_time))
    print('{}, trial_timeout'.format(v.trial_timeout))
    print('{}, start_frequency'.format(v.start_freq_hz))
    print('{}, goal_frequency'.format(v.goal_freq_hz))
    print('{}, base_goal_distance'.format(v.goal_distance_base))
    print('{}, goal_jitter_fraction'.format(v.goal_distance_jitter))
    print('{}, num_steps'.format(v.num_steps))
    print('{}, teleport_prob'.format(v.teleport_prob))
    print('{}, teleport_idxs'.format(v.teleport_idxs))
    print('{}, session_sequence'.format(v.session_sequence))
    print('{}, stim_enabled={}'.format(get_current_time(), v.stim_enabled))
    print('{}, stim_command_codes={}'.format(get_current_time(), v.stim_command_codes))
    print('{}, stim_timing_conditions={}'.format(get_current_time(), v.stim_timing_conditions))
    print('{}, stim_repeats_per_condition={}'.format(get_current_time(), v.stim_repeats_per_condition))
    print('{}, stim_motion_delay_ms={}'.format(get_current_time(), stim_delay_ms()))
    print('{}, stim_cue_step={}'.format(get_current_time(), v.stim_cue_step))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()
    # Session timer starts when a task phase begins.

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

    # STIM: mark session end and close the link.
    print_stim_summary()
    if hasattr(hw, 'bci_link'):
        send_to_stim(v.code_session_marker_to_stim)
        print(
            '{}, sent_session_marker_to_stim code={} phase=end'.format(
                get_current_time(), v.code_session_marker_to_stim
            )
        )
        hw.bci_link.stop()
        print('{}, bci_link_stopped'.format(get_current_time()))

    hw.off()
    print('Session Ended')

# -------------------------------------------------------------------------
# Phase Routing, Spontaneous & Setup States
# -------------------------------------------------------------------------
def phase_router(event):
    if event == 'entry':
        print('Starting configured phase sequence.')
        set_timer('state_timer', 1 * ms)
    elif event == 'state_timer':
        start_current_phase()
    elif event == 'exit':
        disarm_timer('state_timer')

def spontaneous(event):
    if event == 'entry':
        try:
            hw.speaker.off()
        except Exception:
            pass
        try:
            hw.light.all_off()
        except Exception:
            pass
        print(
            'Entering Spontaneous Phase {}/{} ({}s)'.format(
                v.current_phase_index + 1,
                len(v.session_sequence),
                v.spontaneous_duration / second
            )
        )
        set_timer('state_timer', v.spontaneous_duration)
    elif event == 'state_timer':
        advance_phase()
    elif event == 'exit':
        disarm_timer('state_timer')
    elif event == 'motion':
        # Log motion but do nothing else
        v.last_motion_time = get_current_time()

def setup(event):
    if event == 'entry':
        try:
            hw.speaker.off()
        except Exception:
            pass
        try:
            hw.light.all_off()
        except Exception:
            pass
        print('In Setup State. Waiting for manual transition.')
        print('Completed phase: {}. Next phase: {}.'.format(v.completed_phase, current_phase_name()))
        print('To start next phase: Change v.start_next_phase_now to True in Variables tab.')
        v.last_priming_reward_time = get_current_time()
        set_timer('state_timer', 1 * second)
    elif event == 'state_timer':
        if v.start_next_phase_now:
            start_current_phase()
        else:
            set_timer('state_timer', 1 * second)
    elif event == 'lick':
        # Deliver reward if cooldown has elapsed (no sound/LED)
        now = get_current_time()
        if now - v.last_priming_reward_time >= v.priming_reward_cooldown:
            hw.reward.release()
            v.last_priming_reward_time = now
            print('{}, priming_reward_delivered'.format(now))
    elif event == 'exit':
        v.start_next_phase_now = False
        disarm_timer('state_timer')
    elif event == 'motion':
        v.last_motion_time = get_current_time()

# -------------------------------------------------------------------------
# State Machine
# -------------------------------------------------------------------------
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        try:
            hw.light.all_red()
        except:
            pass
        reset_trial()
        v.motion_detected = False
        v.intertrial_start_time = get_current_time()
        set_timer('state_timer', v.intertrial_duration, True)

    elif event == 'motion':
        v.motion_detected = True
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        time_in_intertrial = get_current_time() - v.intertrial_start_time
        if time_in_intertrial >= v.intertrial_duration:
            if not v.motion_detected:
                goto_state('trial')
            else:
                v.motion_detected = False
                set_timer('state_timer', v.motion_wait_time, True)
        else:
            set_timer('state_timer', v.motion_wait_time, True)

    elif event == 'stop_button':
        goto_state('stopped')

    elif event == 'exit':
        # Ensure no intertrial timers bleed into next state
        disarm_timer('state_timer')

def trial(event):
    if event == 'entry':
        # Defensive: clear any lingering state_timer from previous state
        disarm_timer('state_timer')
        disarm_timer('stim_delay_timer')
        try:
            hw.light.cue(3)
        except:
            pass
        hw.speaker.sine(v.start_freq_hz)
        if v.current_stim_timing == 'cue_start':
            trigger_stim('cue_start')
        set_timer('state_timer', v.trial_timeout, True)

    elif event == 'exit':
        disarm_timer('state_timer')
        disarm_timer('stim_delay_timer')
        if v.stim_enabled and not v.stim_sent_this_trial:
            print(
                '{}, stim_trial_not_delivered trial={} timing={} code={} condition={} teleport_type={}'.format(
                    get_current_time(),
                    v.trial_number,
                    v.current_stim_timing,
                    v.current_stim_code,
                    v.current_stim_condition,
                    teleport_type_name()
                )
            )

    elif event == 'motion':
        if not v.first_motion_seen:
            v.first_motion_seen = True
            if v.current_stim_timing == 'first_motion_delay':
                if v.stim_motion_delay <= 0:
                    trigger_stim('first_motion_delay')
                else:
                    set_timer('stim_delay_timer', v.stim_motion_delay, True)
                    print(
                        '{}, stim_delay_started trial={} delay_ms={}'.format(
                            get_current_time(), v.trial_number, stim_delay_ms()
                        )
                    )
        v.current_distance += v.motion_threshold
        update_feedback_from_distance()
        v.last_motion_time = get_current_time()

    elif event == 'stim_delay_timer':
        trigger_stim('first_motion_delay')

    elif event == 'state_timer':
        # Trial timeout without reaching target -> penalty first
        goto_state('penalty')

    elif event == 'stop_button':
        goto_state('stopped')

def reward(event):
    """
    Goal reached. Keep goal tone. Require sustained stillness to enter priming.
    If not still within stop_to_prime_timeout -> penalty.
    """
    if event == 'entry':
        hw.speaker.sine(v.goal_freq_hz)
        v.reward_entry_time = get_current_time()
        set_timer('state_timer', 50 * ms, True)  # periodic check

    elif event == 'exit':
        disarm_timer('state_timer')

    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        now = get_current_time()
        # Check for transition to priming after sufficient stillness
        if now - v.last_motion_time >= v.priming_wait_time:
            goto_state('priming')
        elif now - v.reward_entry_time >= v.stop_to_prime_timeout:
            goto_state('penalty')
        else:
            # Keep checking periodically until either condition is met
            set_timer('state_timer', 50 * ms)

    elif event == 'stop_button':
        goto_state('stopped')

def priming(event):
    """
    LED blinks to signal priming. Lick within priming_window to obtain reward.
    """
    if event == 'entry':
        # Keep goal tone, start LED blinking and window timer
        hw.speaker.sine(v.goal_freq_hz)
        # Target LED index (center when using bilateral mapping)
        v.target_led_percent = 100
        set_led_blinking(True)
        set_timer('state_timer', v.priming_window)

    elif event == 'exit':
        set_led_blinking(False)
        disarm_timer('blink_timer')
        disarm_timer('state_timer')

    elif event == 'blink_timer':
        toggle_led()
        # Reschedule next blink while in priming
        set_timer('blink_timer', v.priming_blink_period)

    elif event == 'lick':
        # Reward available during priming
        v.reward_number += 1
        hw.reward.release()
        print('{}, reward_number'.format(v.reward_number))
        goto_state('post_reward')

    elif event == 'state_timer':
        # Missed lick during priming
        goto_state('penalty')

    elif event == 'stop_button':
        goto_state('stopped')

def penalty(event):
    """
    Lights off and white noise for penalty_duration, then return to intertrial.
    Triggered by: no stop before priming window or no lick during priming.
    """
    if event == 'entry':
        try:
            hw.light.all_off()
        except Exception:
            pass
        hw.speaker.noise(v.penalty_noise_max_freq)
        set_timer('state_timer', v.penalty_duration)

    elif event == 'state_timer':
        goto_state('intertrial')

    elif event == 'exit':
        hw.speaker.off()
        disarm_timer('state_timer')

    elif event == 'stop_button':
        goto_state('stopped')

def post_reward(event):
    """
    Keep goal stimulus on for v.target_present_duration AFTER the reward.
    """
    if event == 'entry':
        # Ensure steady goal sound and target LED (no blinking)
        hw.speaker.sine(v.goal_freq_hz)
        try:
            if not hasattr(v, 'target_led_percent'):
                v.target_led_percent = 100
            hw.light.all_red()
            hw.light.cue(v.target_led_percent)
        except Exception:
            pass
        set_timer('state_timer', v.target_present_duration)

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
        disarm_timer('blink_timer')
        disarm_timer('stim_delay_timer')
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
    # STIM: log markers echoed back by the trigger server, in any state.
    if event == 'cursor_update':
        if hasattr(hw, 'bci_link'):
            log_marker(hw.bci_link.spk)
        return True

    if event == 'session_timer':
        print('Task Phase Timer Expired - Advancing Phase')
        print('{}, total_rewards'.format(v.reward_number))
        advance_phase()
        return True

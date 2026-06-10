from pyControl.utility import *
import hardware_definition as hw
from devices import *
import random

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Modes: 'stationary', 'movement_onset', or 'movement_delay'.
v.test_mode = 'stationary'

v.motion_threshold = 10
v.stationary_hold = 1.5 * second
v.movement_delay = 100 * ms
v.refractory_period = 1.0 * second
v.session_duration = 20 * minute

# Match config.toml [experiments.m1_mapping_low.commands].
v.command_codes = [1, 2, 3, 4]
v.repeats_per_condition = 4

v.block_number = 0
v.trial_number = 0
v.trial_queue = []
v.last_motion_time = 0

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'mode_router',
    'stationary_wait',
    'movement_wait',
    'movement_delay_wait',
    'refractory',
]

events = [
    'session_timer',
    'state_timer',
    'motion',
    'cursor_update',
]

initial_state = 'mode_router'

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def command_name(code):
    if code == 1:
        return 'sham'
    if code == 2:
        return 'left_m1'
    if code == 3:
        return 'right_m1'
    if code == 4:
        return 'bilateral'
    return 'unknown'


def valid_mode():
    if v.test_mode in ['stationary', 'movement_onset', 'movement_delay']:
        return v.test_mode
    print('{}, invalid_test_mode {}; using stationary'.format(get_current_time(), v.test_mode))
    return 'stationary'


def refill_trial_queue():
    new_block = []
    for _ in range(v.repeats_per_condition):
        for code in v.command_codes:
            new_block.append(code)

    for i in range(len(new_block) - 1, 0, -1):
        j = random.randint(0, i)
        new_block[i], new_block[j] = new_block[j], new_block[i]

    v.block_number += 1
    v.trial_queue = new_block
    print(
        '{}, new_stim_block block={} order={}'.format(
            get_current_time(), v.block_number, v.trial_queue
        )
    )


def next_command_code():
    if not v.trial_queue:
        refill_trial_queue()
    return v.trial_queue.pop(0)


def send_stim_command(reason):
    code = next_command_code()
    name = command_name(code)
    v.trial_number += 1

    if hasattr(hw, 'bci_link'):
        hw.bci_link.send_int_to_bci(code)
    else:
        print("!! Error: 'bci_link' not found in hardware_definition.")

    print(
        '{}, stim_trial trial={} block={} mode={} reason={} code={} condition={}'.format(
            get_current_time(),
            v.trial_number,
            v.block_number,
            valid_mode(),
            reason,
            code,
            name,
        )
    )


def goto_wait_state():
    mode = valid_mode()
    if mode == 'stationary':
        goto_state('stationary_wait')
    else:
        goto_state('movement_wait')

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    print('{}, Stim mapping task started'.format(get_current_time()))
    print('{}, test_mode={}'.format(get_current_time(), valid_mode()))
    print('{}, command_codes={}'.format(get_current_time(), v.command_codes))
    print('{}, repeats_per_condition={}'.format(get_current_time(), v.repeats_per_condition))
    print('{}, refractory_period={}'.format(get_current_time(), v.refractory_period))

    if hasattr(hw, 'motionSensor'):
        hw.motionSensor.record()
        hw.motionSensor.threshold = v.motion_threshold
        print('{}, motion_threshold={}'.format(get_current_time(), v.motion_threshold))
    else:
        print("!! Error: 'motionSensor' not found in hardware_definition.")

    if hasattr(hw, 'bci_link'):
        hw.bci_link.start()
        hw.bci_link.send_int_to_bci(0)
        print('{}, sent_session_marker code=0 phase=start'.format(get_current_time()))
    else:
        print("!! Error: 'bci_link' not found in hardware_definition.")

    refill_trial_queue()
    set_timer('session_timer', v.session_duration, True)


def run_end():
    if hasattr(hw, 'motionSensor'):
        hw.motionSensor.stop()
        hw.motionSensor.off()

    if hasattr(hw, 'bci_link'):
        hw.bci_link.send_int_to_bci(0)
        hw.bci_link.stop()
        print('{}, sent_session_marker code=0 phase=end'.format(get_current_time()))

    print('{}, Stim mapping task ended'.format(get_current_time()))

# -------------------------------------------------------------------------
# State Machine
# -------------------------------------------------------------------------
def mode_router(event):
    if event == 'entry':
        goto_wait_state()


def stationary_wait(event):
    if event == 'entry':
        v.last_motion_time = get_current_time()
        reset_timer('state_timer', v.stationary_hold, True)
        print('{}, waiting_for_stationary_hold'.format(get_current_time()))

    elif event == 'motion':
        v.last_motion_time = get_current_time()
        reset_timer('state_timer', v.stationary_hold, True)

    elif event == 'state_timer':
        quiet_time = get_current_time() - v.last_motion_time
        if quiet_time >= v.stationary_hold:
            send_stim_command('stationary_hold')
            goto_state('refractory')
        else:
            reset_timer('state_timer', v.stationary_hold - quiet_time, True)

    elif event == 'exit':
        disarm_timer('state_timer')


def movement_wait(event):
    if event == 'entry':
        print('{}, waiting_for_motion mode={}'.format(get_current_time(), valid_mode()))

    elif event == 'motion':
        v.last_motion_time = get_current_time()
        if valid_mode() == 'movement_delay':
            goto_state('movement_delay_wait')
        else:
            send_stim_command('movement_onset')
            goto_state('refractory')


def movement_delay_wait(event):
    if event == 'entry':
        set_timer('state_timer', v.movement_delay, True)
        print(
            '{}, movement_delay_started delay={}'.format(
                get_current_time(), v.movement_delay
            )
        )

    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'state_timer':
        send_stim_command('movement_delay')
        goto_state('refractory')

    elif event == 'exit':
        disarm_timer('state_timer')


def refractory(event):
    if event == 'entry':
        set_timer('state_timer', v.refractory_period, True)
        print('{}, refractory_started'.format(get_current_time()))

    elif event == 'state_timer':
        goto_wait_state()

    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'exit':
        disarm_timer('state_timer')

# -------------------------------------------------------------------------
# Global Event Handler
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'session_timer':
        print('{}, session_timer_expired trials={}'.format(get_current_time(), v.trial_number))
        stop_framework()

###############################################################################
# Go / No-Go lick task based on Drieu et al. Nature (2025)                   #
###############################################################################
from pyControl.utility import * # seconds, timers, etc.
import hardware_definition as hw
from devices import *
import random                            # randint used in shuffle/ITI

# ------------------------------------------------------------------------- #
#  States and events                                                        #
# ------------------------------------------------------------------------- #
states = ['intertrial', 'no_lick_period', 'stimulus_on', 'dead_period',
          'response_window', 'hit', 'false_alarm', 'miss_cr_delay',
          'timeout']

events = ['session_timer', 'lick', 'no_lick_timer', 'stimulus_timer',
          'dead_period_timer', 'response_timer', 'delay_timer',
          'timeout_timer', 'motion']       # keep if IMU is used

initial_state = 'intertrial'

# ------------------------------------------------------------------------- #
#  Task variables                                                           #
# ------------------------------------------------------------------------- #
# Session timing
v.session_duration = 45 * minute

# Trial structure timing (NEW)
v.no_lick_duration = 1.0 * second    # No lick period (1 s)
v.stimulus_duration = 0.1 * second   # Tone presentation (100 ms)
v.dead_period_duration = 0.2 * second  # Dead period (200 ms)
v.response_window_duration = 2.5 * second # Response period (2.5 s)
v.hit_delay = 4.0 * second           # Hit delay (4 s)
v.miss_cr_delay = 2.0 * second       # Miss and Correct Reject delay (2 s)
v.fa_delay = 7.0 * second            # False Alarm delay (7 s)

# Reward timing
v.reward_duration = 60 * ms            # Duration of single reward pulse

# Frequencies (Hz): index 0 = No-Go, 1 = Go
v.spk_freqs = [2181, 12336]
v.nogo_stim_freq = v.spk_freqs[0]
v.go_stim_freq = v.spk_freqs[1]

# Trial-structure parameters
v.block_size = 20          # trials per mini-block
v.go_fraction = 0.50        # Go probability
v.max_run_length = 4           # never >n identical trials

# ITI parameters
v.min_iti = 5 * second
v.max_iti = 7 * second
v.error_factor = 1.5           # ITI ×1.5 after an error (FA or Miss)

# Inactivity timeout
v.target_duration = 40 * second
v.timeout_duration = 15 * second

# Flags & counters
v.last_trial_outcome = 'CR' # 'Hit', 'Miss', 'FA', 'CR'
v.current_stim_freq = 0
v.correct_go_trials = 0
v.correct_nogo_trials = 0
v.total_go_trials = 0
v.total_nogo_trials = 0
v.is_go_trial = False

# ------------------------------------------------------------------------- #
#  Helper functions                                                         #
# ------------------------------------------------------------------------- #
def shuffle_list(lst):
    "In-place Fisher–Yates shuffle (MicroPython-safe)."
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i]

def max_run_length(seq):
    "Length of the longest stretch of identical values in seq."
    if not seq:
        return 0
    run = best = 1
    last = seq[0]
    for s in seq[1:]:
        if s == last:
            run += 1
            if run > best:
                best = run
        else:
            run, last = 1, s
    return best

def make_block():
    "Build pseudo-random mini-block obeying streak limit."
    n_go = int(v.block_size * v.go_fraction)
    trials = [1] * n_go + [0] * (v.block_size - n_go)
    while True:
        shuffle_list(trials)
        if max_run_length(trials) <= v.max_run_length:
            break
    v.trial_list = trials
    v.trial_i = 0

def choose_iti():
    "Return ITI; increase it after an error (Miss or FA)."
    base = random.randint(v.min_iti, v.max_iti)
    is_error = (v.last_trial_outcome == 'Miss' or v.last_trial_outcome == 'FA')
    return base * v.error_factor if is_error else base

def process_lick():
    """
    Determines the outcome based on a lick event and transitions state.
    Returns True if lick was processed (Hit or FA), False otherwise.
    """
    reset_timer('timeout_timer', v.target_duration)
    if v.is_go_trial:
        goto_state('hit')
        return True
    else:
        goto_state('false_alarm')
        return True
    return False

# ------------------------------------------------------------------------- #
#  Framework hooks                                                          #
# ------------------------------------------------------------------------- #
def run_start():
    hw.reward.reward_duration = v.reward_duration
    hw.speaker.set_volume(10)
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    set_timer('session_timer', v.session_duration, True)
    set_timer('timeout_timer', v.target_duration)
    hw.cameraTrigger.start()
    make_block()
    print('{}, Session Started'.format(get_current_time()))
    print('{}, CPI {}'.format(get_current_time(), hw.motionSensor.sensor_x.CPI))

def run_end():
    hw.speaker.off()
    hw.reward.stop()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()

    total = v.total_go_trials + v.total_nogo_trials
    go_p = 100 * v.correct_go_trials / max(1, v.total_go_trials)
    nogo_p = 100 * v.correct_nogo_trials / max(1, v.total_nogo_trials)
    overall_p = 100 * (v.correct_go_trials + v.correct_nogo_trials) / max(1, total)

    print('Session Ended')
    print('Go (Hit) : {}/{} ({:.2f}%)'.format(v.correct_go_trials, v.total_go_trials, go_p))
    print('NoGo (CR): {}/{} ({:.2f}%)'.format(v.correct_nogo_trials, v.total_nogo_trials, nogo_p))
    print('Overall : {}/{} ({:.2f}%)'.format(v.correct_go_trials + v.correct_nogo_trials,
                                             total, overall_p))

# ------------------------------------------------------------------------- #
#  States                                                                   #
# ------------------------------------------------------------------------- #
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        iti = choose_iti()
        print('{}, ITI: {:.2f}s'.format(get_current_time(), iti / second))
        timed_goto_state('no_lick_period', iti)

    elif event == 'lick':
        reset_timer('timeout_timer', v.target_duration)

    elif event == 'timeout_timer':
        goto_state('timeout')

# ------------------------------------------------------------------------- #
def no_lick_period(event):
    if event == 'entry':
        print('{}, No Lick Period Started'.format(get_current_time()))
        set_timer('no_lick_timer', v.no_lick_duration)

    elif event == 'lick':
        print('{}, Lick during No Lick Period - Resetting'.format(get_current_time()))
        reset_timer('no_lick_timer', v.no_lick_duration)
        reset_timer('timeout_timer', v.target_duration)

    elif event == 'no_lick_timer':
        goto_state('stimulus_on')

    elif event == 'exit':
        disarm_timer('no_lick_timer')

# ------------------------------------------------------------------------- #
def stimulus_on(event):
    if event == 'entry':
        # Choose trial type
        trial_type = v.trial_list[v.trial_i]
        v.trial_i += 1
        if v.trial_i >= len(v.trial_list):
            make_block()

        v.is_go_trial = (trial_type == 1)
        v.current_stim_freq = v.go_stim_freq if v.is_go_trial else v.nogo_stim_freq
        
        if v.is_go_trial:
            v.total_go_trials += 1
            print('{}, Go Trial {} ({:.0f} Hz)'.format(get_current_time(), v.total_go_trials, v.current_stim_freq))
        else:
            v.total_nogo_trials += 1
            print('{}, NoGo Trial {} ({:.0f} Hz)'.format(get_current_time(), v.total_nogo_trials, v.current_stim_freq))

        hw.speaker.sine(v.current_stim_freq)
        set_timer('stimulus_timer', v.stimulus_duration)

    elif event == 'lick':
        # Allow early licks during stim presentation (can be FA or Hit)
        process_lick()

    elif event == 'stimulus_timer':
        hw.speaker.off()
        goto_state('dead_period')

    elif event == 'exit':
        disarm_timer('stimulus_timer')

# ------------------------------------------------------------------------- #
def dead_period(event):
    if event == 'entry':
        set_timer('dead_period_timer', v.dead_period_duration)

    elif event == 'lick':
        # Allow early licks during dead period (can be FA or Hit)
        process_lick()

    elif event == 'dead_period_timer':
        goto_state('response_window')

    elif event == 'exit':
        disarm_timer('dead_period_timer')

# ------------------------------------------------------------------------- #
def response_window(event):
    if event == 'entry':
        print('{}, Response Window Opened'.format(get_current_time()))
        set_timer('response_timer', v.response_window_duration)

    elif event == 'lick':
        process_lick()

    elif event == 'response_timer':
        # No lick occurred during the response window
        if v.is_go_trial:
            # Miss
            v.last_trial_outcome = 'Miss'
            print('{}, Miss ({}/{} Go Trials)'.format(get_current_time(), v.correct_go_trials, v.total_go_trials))
            goto_state('miss_cr_delay')
        else:
            # Correct Reject
            v.correct_nogo_trials += 1
            v.last_trial_outcome = 'CR'
            print('{}, Correct Reject ({}/{} NoGo Trials)'.format(get_current_time(), v.correct_nogo_trials, v.total_nogo_trials))
            goto_state('miss_cr_delay')

    elif event == 'exit':
        disarm_timer('response_timer')

# ------------------------------------------------------------------------- #
def hit(event):
    if event == 'entry':
        hw.reward.release()
        v.correct_go_trials += 1
        v.last_trial_outcome = 'Hit'
        print('{}, Hit! ({}/{} Go Trials) - Delay: {}s'.format(get_current_time(), v.correct_go_trials, v.total_go_trials, v.hit_delay/second))
        reset_timer('timeout_timer', v.target_duration)
        set_timer('delay_timer', v.hit_delay)

    elif event == 'delay_timer':
        goto_state('intertrial')

    elif event == 'lick': # Allow licking during delay
        reset_timer('timeout_timer', v.target_duration)

    elif event == 'exit':
        disarm_timer('delay_timer')

# ------------------------------------------------------------------------- #
def false_alarm(event):
    if event == 'entry':
        v.last_trial_outcome = 'FA'
        print('{}, False Alarm - Timeout: {}s'.format(get_current_time(), v.fa_delay/second))
        set_timer('delay_timer', v.fa_delay)
        # Note: No 'punishment_on' logic as per new requirements.

    elif event == 'delay_timer':
        goto_state('intertrial')

    elif event == 'lick': # Licks during FA timeout reset inactivity timer
        reset_timer('timeout_timer', v.target_duration)

    elif event == 'exit':
        disarm_timer('delay_timer')

# ------------------------------------------------------------------------- #
def miss_cr_delay(event):
    if event == 'entry':
        print('{}, Miss/CR Delay: {}s'.format(get_current_time(), v.miss_cr_delay/second))
        set_timer('delay_timer', v.miss_cr_delay)

    elif event == 'delay_timer':
        goto_state('intertrial')

    elif event == 'lick': # Licks during delay reset inactivity timer
        reset_timer('timeout_timer', v.target_duration)

    elif event == 'exit':
        disarm_timer('delay_timer')

# ------------------------------------------------------------------------- #
def timeout(event):
    if event == 'entry':
        hw.speaker.off()
        print('{}, Inactivity Timeout'.format(get_current_time()))
        timed_goto_state('intertrial', v.timeout_duration)

    elif event == 'exit':
        reset_timer('timeout_timer', v.target_duration)

# ------------------------------------------------------------------------- #
def all_states(event):
    if event == 'session_timer':
        stop_framework()
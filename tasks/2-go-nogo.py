###############################################################################
# Go / No-Go lick task – Last updated (30-Apr-2025)                #
###############################################################################
from pyControl.utility import *          # seconds, timers, etc.
import hardware_definition as hw
from devices import *
import random                            # randint used in shuffle/ITI

# ------------------------------------------------------------------------- #
#  States and events                                                        #
# ------------------------------------------------------------------------- #
states = ['intertrial', 'stimulus_on', 'response_window',
          'reward', 'punish_timeout', 'timeout']

events = ['session_timer', 'lick',
          'stimulus_timer', 'response_timer',
          'punish_timeout_timer', 'timeout_timer',
          'motion']                      # keep if IMU is used

initial_state = 'intertrial'

# ------------------------------------------------------------------------- #
#  Task variables                                                           #
# ------------------------------------------------------------------------- #
# Session timing
v.session_duration       = 45 * minute

# Stimulus & response timing
v.stimulus_duration      = 0.5 * second
v.response_window        = 2.5 * second
v.reward_duration        = 60  * ms
v.reward_period_duration = 0.5 * second

# Frequencies (Hz): index 0 = No-Go, 1 = Go
v.spk_freqs      = [2181, 12336]
v.nogo_stim_freq = v.spk_freqs[0]
v.go_stim_freq   = v.spk_freqs[1]

# Trial-structure parameters
v.block_size     = 20          # trials per mini-block
v.go_fraction    = 0.50        # Go probability
v.max_run_length = 4           # never >n identical trials

# ITI parameters
v.min_iti        = 5 * second
v.max_iti        = 7 * second
v.error_factor   = 1.5           # ITI ×2 after an error

# Punishment timeout
v.punish_timeout_duration = 0.5 * second
v.punishment_on           = False      # if True, lick resets timeout

# Inactivity timeout
v.target_duration = 40 * second
v.timeout_duration = 15 * second

# Flags & counters
v.last_trial_correct  = True
v.current_stim_freq   = 0
v.correct_go_trials   = 0
v.correct_nogo_trials = 0
v.total_go_trials     = 0
v.total_nogo_trials   = 0

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
    n_go   = int(v.block_size * v.go_fraction)
    trials = [1] * n_go + [0] * (v.block_size - n_go)
    while True:
        shuffle_list(trials)
        if max_run_length(trials) <= v.max_run_length:
            break
    v.trial_list = trials
    v.trial_i    = 0

def choose_iti(correct=True):
    "Return ITI; double it after an error."
    base = random.randint(v.min_iti, v.max_iti)
    return base if correct else base * v.error_factor

# ------------------------------------------------------------------------- #
#  Framework hooks                                                          #
# ------------------------------------------------------------------------- #
def run_start():
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    hw.speaker.set_volume(10)
    hw.light.start()
    hw.light.off()
    make_block()
    set_timer('session_timer', v.session_duration, True)
    set_timer('timeout_timer', v.target_duration)
    hw.cameraTrigger.start()
    print('{}, Session Started'.format(get_current_time()))
    print('{}, CPI {}'.format(get_current_time(), hw.motionSensor.sensor_x.CPI))

def run_end():
    hw.light.off()
    hw.speaker.off()
    hw.reward.stop()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()

    total = v.total_go_trials + v.total_nogo_trials
    go_p   = 100 * v.correct_go_trials   / max(1, v.total_go_trials)
    nogo_p = 100 * v.correct_nogo_trials / max(1, v.total_nogo_trials)
    overall_p = 100 * (v.correct_go_trials+v.correct_nogo_trials) / max(1, total)

    print('Session Ended')
    print('Go   : {}/{}   ({:.2f}%)'.format(v.correct_go_trials,   v.total_go_trials,   go_p))
    print('NoGo : {}/{} ({:.2f}%)'.format(v.correct_nogo_trials, v.total_nogo_trials, nogo_p))
    print('Overall : {}/{} ({:.2f}%)'.format(v.correct_go_trials+v.correct_nogo_trials,
                                             total, overall_p))

# ------------------------------------------------------------------------- #
#  States                                                                   #
# ------------------------------------------------------------------------- #
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        iti = choose_iti(v.last_trial_correct)
        timed_goto_state('stimulus_on', iti)

    elif event == 'lick':
        reset_timer('timeout_timer', v.target_duration)

    elif event == 'timeout_timer':
        goto_state('timeout')

# ------------------------------------------------------------------------- #
def stimulus_on(event):
    if event == 'entry':
        # choose trial type
        trial_type = v.trial_list[v.trial_i]
        v.trial_i += 1
        if v.trial_i >= len(v.trial_list):
            make_block()

        v.current_stim_freq = v.go_stim_freq if trial_type else v.nogo_stim_freq
        hw.speaker.sine(v.current_stim_freq)
        print('{}, frequency {}'.format(get_current_time(), v.current_stim_freq))
        set_timer('stimulus_timer', v.stimulus_duration)

        if v.current_stim_freq == v.go_stim_freq:
            v.total_go_trials += 1
        else:
            v.total_nogo_trials += 1

    elif event == 'lick':
        # hw.speaker.off()
        # disarm_timer('stimulus_timer')
        v.last_trial_correct = (v.current_stim_freq == v.go_stim_freq)
        goto_state('reward' if v.last_trial_correct else 'punish_timeout')

    elif event == 'stimulus_timer':
        hw.speaker.off()
        goto_state('response_window')

# ------------------------------------------------------------------------- #
def response_window(event):
    if event == 'entry':
        set_timer('response_timer', v.response_window)

    elif event == 'lick':
        v.last_trial_correct = (v.current_stim_freq == v.go_stim_freq)
        goto_state('reward' if v.last_trial_correct else 'punish_timeout')

    elif event == 'response_timer':          # withholding complete
        if v.current_stim_freq == v.nogo_stim_freq:
            v.correct_nogo_trials += 1
            print('Correct NoGo trials: {}/{}'.format(v.correct_nogo_trials,
                                                      v.total_nogo_trials))
            v.last_trial_correct = True
        else:
            v.last_trial_correct = False
        goto_state('intertrial')

# ------------------------------------------------------------------------- #
def reward(event):
    if event == 'entry':
        hw.reward.release()
        v.correct_go_trials += 1
        v.last_trial_correct = True
        print('reward number {}/{}'.format(v.correct_go_trials, v.total_go_trials))
        reset_timer('timeout_timer', v.target_duration)
        timed_goto_state('intertrial', v.reward_period_duration)

# ------------------------------------------------------------------------- #
def punish_timeout(event):
    if event == 'entry':
        v.last_trial_correct = False
        print('Punishment Timeout Started ({}s)'.format(v.punish_timeout_duration/second))
        set_timer('punish_timeout_timer', v.punish_timeout_duration)

    elif event == 'lick':
        print('Lick during punishment timeout - Resetting timer')
        if v.punishment_on:
            reset_timer('punish_timeout_timer', v.punish_timeout_duration)
        reset_timer('timeout_timer', v.target_duration)

    elif event == 'punish_timeout_timer':
        reset_timer('timeout_timer', v.target_duration)
        goto_state('intertrial')
        # goto_state('stimulus_on')

    elif event == 'exit':
        disarm_timer('punish_timeout_timer')

# ------------------------------------------------------------------------- #
def timeout(event):
    if event == 'entry':
        hw.speaker.off()
        timed_goto_state('intertrial', v.timeout_duration)

    elif event == 'exit':
        reset_timer('timeout_timer', v.target_duration)

# ------------------------------------------------------------------------- #
def all_states(event):
    if event == 'session_timer':
        stop_framework()

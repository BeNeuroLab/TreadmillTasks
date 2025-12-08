###############################################################################
# Operant lick task (Go-only) – Last updated (08-Dec-2025)                    #
###############################################################################
from pyControl.utility import *          # seconds, timers, etc.
import hardware_definition as hw
from devices import *
import random                            # randint used in shuffle/ITI

# ------------------------------------------------------------------------- #
#  States and events                                                        #
# ------------------------------------------------------------------------- #
states = ['intertrial', 'stimulus_on', 'response_window',
          'reward', 'timeout']

events = ['session_timer', 'lick',
          'stimulus_timer', 'response_timer',
          'timeout_timer',
          'motion']                      # keep if IMU is used

initial_state = 'intertrial'

# ------------------------------------------------------------------------- #
#  Task variables                                                           #
# ------------------------------------------------------------------------- #
# Session timing
v.session_duration       = 45 * minute

# Stimulus & response timing
v.stimulus_duration      = 1 * second
v.response_window        = 2.5 * second
v.reward_duration        = 30  * ms
v.reward_period_duration = 0.5 * second

# Frequencies (Hz): index 0 = No-Go, 1 = Go
v.spk_freqs      = [2000, 10000]
v.go_stim_freq   = v.spk_freqs[1]

# ITI parameters
v.min_iti        = 2 * second
v.max_iti        = 3 * second
v.error_factor   = 1.0           # ITI ×2 after an error

# Inactivity timeout
v.target_duration = 40 * second
v.timeout_duration = 15 * second

# Flags & counters
v.last_trial_correct  = True
v.correct_go_trials   = 0
v.total_go_trials     = 0

# ------------------------------------------------------------------------- #
#  Helper functions                                                         #
# ------------------------------------------------------------------------- #
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

    go_p   = 100 * v.correct_go_trials   / max(1, v.total_go_trials)

    print('Session Ended')
    print('Go   : {}/{}   ({:.2f}%)'.format(v.correct_go_trials,   v.total_go_trials,   go_p))

# ------------------------------------------------------------------------- #
#  States                                                                   #
# ------------------------------------------------------------------------- #
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        hw.light.off() # Ensure LED is off
        iti = choose_iti(v.last_trial_correct)
        timed_goto_state('stimulus_on', iti)

    elif event == 'lick':
        reset_timer('timeout_timer', v.target_duration)

    elif event == 'timeout_timer':
        goto_state('timeout')

# ------------------------------------------------------------------------- #
def stimulus_on(event):
    if event == 'entry':
        hw.speaker.sine(v.go_stim_freq)
        hw.light.cue(50) # Center LED
        print('{}, frequency {}'.format(get_current_time(), v.go_stim_freq))
        set_timer('stimulus_timer', v.stimulus_duration)

        v.total_go_trials += 1

    elif event == 'lick':
        v.last_trial_correct = True
        goto_state('reward')

    elif event == 'stimulus_timer':
        hw.speaker.off()
        hw.light.off() # Turn off LED after stimulus duration? Or keep it on during response window? 
                       # Usually stimulus duration implies stimulus is on. 
                       # But if response window is separate, maybe LED should stay on?
                       # In 2-go-nogo, speaker turns off at stimulus_timer.
                       # I will turn off LED here too to match "stimulus duration".
        goto_state('response_window')

# ------------------------------------------------------------------------- #
def response_window(event):
    if event == 'entry':
        set_timer('response_timer', v.response_window)

    elif event == 'lick':
        v.last_trial_correct = True
        goto_state('reward')

    elif event == 'response_timer':          # withholding complete -> Miss
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
def timeout(event):
    if event == 'entry':
        hw.speaker.off()
        hw.light.off()
        timed_goto_state('intertrial', v.timeout_duration)

    elif event == 'exit':
        reset_timer('timeout_timer', v.target_duration)

# ------------------------------------------------------------------------- #
def all_states(event):
    if event == 'session_timer':
        stop_framework()

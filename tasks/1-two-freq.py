from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
 
# States
states = ['intertrial', 'stimulus_on', 'reward', 'timeout']
 
# Events
events = ['session_timer', 'lick', 'stimulus_timer', 'timeout_timer']
 
# Initial state
initial_state = 'intertrial'

# -------------------------------------------------------------------------
 
# Variables
v.session_duration = 45 * minute
v.stimulus_duration = 2 * second
v.reward_duration = 40 * ms
v.iti_duration = 5 * second  # Inter-trial interval
v.spk_freqs = [2181, 12336]
v.correct_trials = 0
v.total_trials = 0

v.target_duration = 40 * second
v.timeout_duration = 15 * second

# -------------------------------------------------------------------------
 
def run_start():
    hw.reward.reward_duration = v.reward_duration
    hw.speaker.set_volume(10)
    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration)
    print('Session started')
    set_timer('timeout_timer',v.target_duration)
 
def run_end():
    hw.speaker.off()
    hw.reward.stop()
    hw.cameraTrigger.stop()
    print('Session ended. Correct trials: {}/{}'.format(v.correct_trials, v.total_trials))
 
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        timed_goto_state('stimulus_on', v.iti_duration)
    elif event == 'lick':
        reset_timer('timeout_timer',v.target_duration)
    elif event == 'timeout_timer':
        goto_state('timeout')
 
def stimulus_on(event):
    if event == 'entry':
        v.total_trials += 1
        v.sound_target = choice(v.spk_freqs)
        hw.speaker.sine(v.sound_target)
        set_timer('stimulus_timer', v.stimulus_duration)
    elif event == 'lick':
        goto_state('reward')
    elif event == 'timeout_timer':
        goto_state('timeout')
    elif event == 'stimulus_timer':
        hw.speaker.off()
        goto_state('intertrial')
        
def reward(event):
    if event == 'entry':
        hw.reward.release()
        v.correct_trials += 1
        print('reward number {}/{} ({})'.format(v.correct_trials, v.total_trials, v.spk_freqs))
        timed_goto_state('intertrial', 1000)
        reset_timer('timeout_timer',v.target_duration)
        
def timeout(event):
    "timeout state"
    if event == 'entry':
        hw.speaker.off()
        timed_goto_state('intertrial', v.timeout_duration)
    elif event == 'exit':
        reset_timer('timeout_timer',v.target_duration)
 
def all_states(event):
    if event == 'session_timer':
        stop_framework()
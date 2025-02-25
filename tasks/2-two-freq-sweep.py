from pyControl.utility import *
import hardware_definition as hw
from devices import *
import random

# -------------------------------------------------------------------------
 
# States
states = ['intertrial', 'stimulus_on', 'reward', 'timeout', 'reward_freq']
 
# Events
events = ['session_timer', 'sweep_timer', 'lick', 'stimulus_timer', 'timeout_timer']
 
# Initial state
initial_state = 'intertrial'

# -------------------------------------------------------------------------
 
# Variables
v.session_duration = 5 * minute
v.stimulus_duration = 2 * second
v.sweep_duration = .15 * second
v.reward_duration = 40 * ms
v.iti_duration = 8 * second  # Inter-trial interval
# v.spk_freqs = [2181,2378,2594,2828,3084,3364,3668,4000,4362,4757,5187,5657,6169,6727,7336,8000,8724,9514,10375,11314,12336]  # Frequency sweep range
v.spk_freqs = [2181,2594,3084,3668,4362,5187,6169,7336,8724,10375,12338] # 4tr octave list

v.trial_in_block = 2  # Track position within the block
v.correct_trials = 0
v.total_trials = 0

v.target_duration = 40 * second
v.timeout_duration = 15 * second

# Define frequency progression
mid_idx = len(v.spk_freqs) // 2  # Index of middle frequency
v.current_freq_index = mid_idx  # Start from the middle frequency

# Pseudo-randomized trial structure
v.trial_types = ['ascending', 'descending']  # Both must appear in every block

# -------------------------------------------------------------------------

def shuffle_list(lst): # Fisher-Yates Shuffle
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i]  # Swap elements

# -------------------------------------------------------------------------        

def run_start():
    hw.reward.reward_duration = v.reward_duration
    hw.speaker.set_volume(10)
    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration)
    print('Session started')
    set_timer('timeout_timer', v.target_duration)
 
def run_end():
    hw.speaker.off()
    hw.reward.stop()
    hw.cameraTrigger.stop()
    print('Session ended. Correct trials: {}/{}'.format(v.correct_trials, v.total_trials))
 
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        timed_goto_state('stimulus_on', v.iti_duration)
        if v.trial_in_block >= 2:  # End of block, reset and shuffle
            v.trial_in_block = 0
            shuffle_list(v.trial_types)  # Shuffle order of next block
    elif event == 'lick':
        reset_timer('timeout_timer', v.target_duration)
    elif event == 'timeout_timer':
        goto_state('timeout')

def stimulus_on(event):
    if event == 'entry':
        v.total_trials += 1
        v.trial_type = v.trial_types[v.trial_in_block] # Select trial type from the shuffled block
        v.current_freq_index = mid_idx # Set initial frequency for this trial
        hw.speaker.sine(v.spk_freqs[v.current_freq_index])
        set_timer('sweep_timer', v.sweep_duration)
    elif event == 'sweep_timer':
        if v.trial_type == 'ascending':
            v.current_freq_index += 1
        else:  # Descending trial
            v.current_freq_index -= 1
        hw.speaker.sine(v.spk_freqs[v.current_freq_index])
        if v.spk_freqs[v.current_freq_index] in [min(v.spk_freqs), max(v.spk_freqs)]:  # Reward at terminal freq
            goto_state('reward_freq')
        else:
            set_timer('sweep_timer', v.sweep_duration)   
    elif event == 'lick':
        print("Premature lick, no reward")

def reward_freq (event):
    "reward state"
    if event == 'entry':
        set_timer('stimulus_timer', v.stimulus_duration)
    elif event == 'lick':
        goto_state('reward')
    elif event == 'stimulus_timer':
        hw.speaker.off()
        v.trial_in_block += 1  # Move to next trial in block
        goto_state('intertrial')

def reward(event):
    if event == 'entry':
        hw.reward.release()
        v.correct_trials += 1
        print('reward number {}/{} ({})'.format(v.correct_trials, v.total_trials, v.trial_type))
        timed_goto_state('intertrial', 1000)
        reset_timer('timeout_timer', v.target_duration)
        v.trial_in_block += 1  # Move to next trial in block

def timeout(event):
    if event == 'entry':
        hw.speaker.off()
        timed_goto_state('intertrial', v.timeout_duration)
    elif event == 'exit':
        reset_timer('timeout_timer', v.target_duration)
 
def all_states(event):
    if event == 'session_timer':
        stop_framework()

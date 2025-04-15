from pyControl.utility import *
import hardware_definition as hw
from devices import *
import random

# -------------------------------------------------------------------------
 
# States
states = ['intertrial', 'stimulus_on', 'reward', 'timeout', 'reward_freq']
 
# Events
events = ['session_timer', 'sweep_timer', 'lick', 'stimulus_timer', 'motion','timeout_timer']
 
# Initial state
initial_state = 'intertrial'

# -------------------------------------------------------------------------
 
# Variables
v.session_duration = 45 * minute
v.stimulus_duration = 2 * second
v.sweep_duration_range = [.1, .2] # seconds
v.reward_duration = 40 * ms
v.reward_period_duration = 2 * second
v.iti_duration = 5 * second  # Inter-trial interval
# v.spk_freqs = [2181,2378,2594,2828,3084,3364,3668,4000,4362,4757,5187,5657,6169,6727,7336,8000,8724,9514,10375,11314,12336]  # Frequency sweep range
v.spk_freqs = [2181,2594,3084,3668,4362,5187,6169,7336,8724,10375,12338] # 4tr octave list
v.leds_left = [2] # left leds to turn on
v.leds_right = [4] # right leds to turn on

v.trial_in_block = 0  # Track position within the block
v.correct_trials = 0
v.total_trials = 0

v.target_duration = 40 * second
v.timeout_duration = 15 * second

# Define frequency progression
mid_idx = len(v.spk_freqs) // 2  # Index of middle frequency
v.current_freq_index = mid_idx  # Start from the middle frequency

# Block configuration:
v.reward_ratio = 1   # For example, 2 rewarded trials per rewarded type (can be set to 1, 2, 3, …)
# v.block_size = 2 * v.reward_ratio + 2


# -------------------------------------------------------------------------

def shuffle_list(lst): # Fisher-Yates Shuffle
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i]  # Swap elements

# -------------------------------------------------------------------------
 
def build_trial_block():
    """
    Construct a block of trial types based on v.reward_ratio.
    Each rewarded trial type ('ascending' and 'descending') is repeated v.reward_ratio times,
    and each catch trial type ('ascending catch' and 'descending catch') appears once.
    The block size is thus: 2*v.reward_ratio + 2.
    """
    rewarded_count_per_type = v.reward_ratio
    catch_count_per_type = 1
    trial_block = (['ascending'] * rewarded_count_per_type +
                   ['descending'] * rewarded_count_per_type +
                   ['ascending catch'] * catch_count_per_type +
                   ['descending catch'] * catch_count_per_type)
    shuffle_list(trial_block)
    return trial_block

# -------------------------------------------------------------------------        

def run_start():
    hw.speaker.set_volume(10)
    hw.cameraTrigger.start()
    hw.light.all_off()
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    hw.reward.reward_duration = v.reward_duration

    # Build the initial block of trials.
    v.block_size = 2 * v.reward_ratio + 2
    v.trial_types = build_trial_block()

    set_timer('session_timer', v.session_duration)
    set_timer('timeout_timer', v.target_duration)
    print('{}, before_camera_trigger'.format(get_current_time()))
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    hw.cameraTrigger.start()
 
def run_end():
    hw.speaker.off()
    hw.light.all_off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    print('session_ended_correct_trials_{}/{}'.format(v.correct_trials, v.total_trials))
 
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        hw.light.all_off()
        timed_goto_state('stimulus_on', v.iti_duration)
        # At the end of the block, reset the counter and build a new randomized block.
        if v.trial_in_block >= v.block_size:
            v.trial_in_block = 0
            v.trial_types = build_trial_block()
    elif event == 'lick':
        reset_timer('timeout_timer', v.target_duration)
    elif event == 'timeout_timer':
        goto_state('timeout')

def stimulus_on(event):
    if event == 'entry':
        v.total_trials += 1
        v.trial_type = v.trial_types[v.trial_in_block] # Select trial type from the shuffled block
        v.current_freq_index = mid_idx # Set initial frequency for this trial   
        v.sweep_duration = random.uniform(v.sweep_duration_range[0], v.sweep_duration_range[1]) * second # Set random sweep duration between 0.1 and 0.2 seconds
        hw.speaker.sine(v.spk_freqs[v.current_freq_index])
        set_timer('sweep_timer', v.sweep_duration)
        if v.trial_type == 'ascending':
            hw.light.cue_array(v.leds_right)
            print('{}, trial_type'.format(0))
            print('ascending rewarded')
        elif v.trial_type == 'descending':
            hw.light.cue_array(v.leds_left)
            print('{}, trial_type'.format(1))
            print('descending rewarded')
        elif v.trial_type == 'ascending catch':
            hw.light.cue_array(v.leds_left)
            print('{}, trial_type'.format(2))
            print('ascending catch')
        elif v.trial_type == 'descending catch':
            hw.light.cue_array(v.leds_right)
            print('{}, trial_type'.format(3))
            print('descending catch')
        
    elif event == 'sweep_timer':
        if 'ascending' in v.trial_type: 
            v.current_freq_index += 1
        else:  # Descending trial
            v.current_freq_index -= 1
        hw.speaker.sine(v.spk_freqs[v.current_freq_index])
        if v.spk_freqs[v.current_freq_index] in [min(v.spk_freqs), max(v.spk_freqs)]:  # Reward at terminal freq
            goto_state('reward_freq')
        else:
            set_timer('sweep_timer', v.sweep_duration)   
    # elif event == 'lick':
    #     print("premature_lick_no_reward")

def reward_freq (event):
    #"reward state (rewarded trials)"
    if event == 'entry':
        set_timer('stimulus_timer', v.stimulus_duration)
    elif event == 'lick':
        if v.trial_type in ['ascending', 'descending']:
            goto_state('reward')
        else:
            print('Lick received in catch trial: no reward')
    elif event == 'stimulus_timer':
        hw.speaker.off()
        hw.light.all_off()
        v.trial_in_block += 1  # Move to next trial in block
        goto_state('intertrial')

def reward(event):
    if event == 'entry':
        hw.reward.release()
        v.correct_trials += 1
        print('{}, reward_number'.format(v.correct_trials))
        timed_goto_state('intertrial', v.reward_period_duration)
        reset_timer('timeout_timer', v.target_duration)
        v.trial_in_block += 1  # Move to next trial in block

def timeout(event):
    if event == 'entry':
        hw.speaker.off()
        hw.light.all_off()
        timed_goto_state('intertrial', v.timeout_duration)
    elif event == 'exit':
        reset_timer('timeout_timer', v.target_duration)
 
def all_states(event):
    if event == 'session_timer':
        stop_framework()

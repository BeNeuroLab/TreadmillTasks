from pyControl.utility import *
import hardware_definition as hw
from devices import *
 
# States
states = ['wait_for_trial', 'stimulus_on', 'reward', 'timeout','silence']
 
# Events
events = ['session_timer', 'trial_timer', 'lick', 'stimulus_timer', 'led_timer']
 
# Initial state
initial_state = 'wait_for_trial'
 
# Variables
v.session_duration = 30 * minute
v.trial_duration = 2 * second
v.stimulus_duration = 2 * second
v.reward_duration = 40 * ms
v.timeout_duration = 2 * second
v.iti_duration = 3 * second  # Inter-trial interval
v.reward_led_duration = 1 * second
v.targets = [2, 4]  # Speaker/LED positions
v.correct_trials = 0
v.total_trials = 0
v.mismatch_percentage = 30  # Percentage of trials that should be mismatched
v.mismatch_trials = 0

v.target_duration = 45 * second
v.silence_duration = 15 * second
 
def run_start():
    hw.reward.reward_duration = v.reward_duration
    hw.sound.set_volume(8)  # Adjust as needed
    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration)
    print('Session started')
    set_timer('led_timer',v.target_duration)
 
def run_end():
    hw.sound.stop()
    hw.light.all_off()
    hw.reward.stop()
    hw.cameraTrigger.stop()
    print('Session ended. Correct trials: {}/{}'.format(v.correct_trials, v.total_trials))
 
def wait_for_trial(event):
    if event == 'entry':
        hw.sound.all_off()
        hw.light.all_off()
        timed_goto_state('stimulus_on', v.iti_duration)
    elif event == 'lick':
        reset_timer('led_timer',v.iti_duration)
    elif event == 'led_timer':
        goto_state('silence')
 
def stimulus_on(event):
    if event == 'entry':
        v.total_trials += 1
        # Determine if this trial should be mismatched
        if (v.mismatch_trials / v.total_trials) * 100 < v.mismatch_percentage:
            v.should_mismatch = withprob(0.8)  # 80% chance to mismatch if we're below the target percentage
        else:
            v.should_mismatch = withprob(0)  # 10% chance to mismatch if we're at or above the target percentage

        v.sound_target = choice(v.targets)       
        if v.should_mismatch:
            v.light_target = [t for t in v.targets if t != v.sound_target][0]
            v.mismatch_trials += 1
        else:
            v.light_target = v.sound_target        
        hw.sound.cue(v.sound_target)
        hw.light.cue(v.light_target)
        v.matching = v.sound_target == v.light_target
        print('Trial {} started. Sound: {}, Light: {}, Matching: {}'.format(
            v.total_trials, v.sound_target, v.light_target, v.matching))
        set_timer('stimulus_timer', v.stimulus_duration)
        set_timer('trial_timer', v.trial_duration)
    elif event == 'lick':
        if v.matching:
            goto_state('reward')
    elif event == 'led_timer':
        goto_state('silence')
    elif event == 'stimulus_timer':
        hw.sound.all_off()
        hw.light.all_off()
    elif event == 'trial_timer':
        goto_state('wait_for_trial')
 
def reward(event):
    if event == 'entry':
        hw.reward.release()
        
        #hw.sound.all_off()
        #hw.light.all_off()
        v.correct_trials += 1
        print('Correct! Trials: {}/{}'.format(v.correct_trials, v.total_trials))
        timed_goto_state('wait_for_trial', v.reward_led_duration)
        reset_timer('led_timer',v.target_duration)
 
def timeout(event):
    if event == 'entry':
        hw.sound.all_off()
        hw.light.all_off()
        print('Incorrect. Trials: {}/{}'.format(v.correct_trials, v.total_trials))
        timed_goto_state('wait_for_trial', v.timeout_duration)
        
def silence(event):
    "silence state"
    if event == 'entry':
        hw.light.all_off()
        hw.sound.all_off()
        timed_goto_state('wait_for_trial', v.silence_duration)
    elif event == 'exit':
        reset_timer('led_timer',v.target_duration)
 
def all_states(event):
    if event == 'session_timer':
        stop_framework()
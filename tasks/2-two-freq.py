from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
 
# States
states = ['intertrial', 'stimulus_on', 'reward', 'timeout']
 
# Events
events = ['session_timer', 'lick', 'stimulus_timer','motion', 'timeout_timer']
 
# Initial state
initial_state = 'intertrial'

# -------------------------------------------------------------------------
 
# Variables
v.session_duration = 45 * minute
v.stimulus_duration = 2 * second
v.reward_duration = 50 * ms
v.iti_duration = 4 * second  # Inter-trial interval
v.spk_freqs = [2181, 12336]
v.leds = [2, 4]
v.correct_trials = 0
v.total_trials = 0

v.target_duration = 40 * second
v.timeout_duration = 15 * second

# -------------------------------------------------------------------------
 
def run_start():
    hw.reward.reward_duration = v.reward_duration
    hw.speaker.set_volume(10)
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    set_timer('session_timer', v.session_duration, True)
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
    print('Session ended. Correct trials: {}/{}'.format(v.correct_trials, v.total_trials))
 
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        hw.light.all_off()
        timed_goto_state('stimulus_on', v.iti_duration)
    elif event == 'lick':
        reset_timer('timeout_timer',v.target_duration)
    elif event == 'timeout_timer':
        goto_state('timeout')
 
def stimulus_on(event):
    if event == 'entry':
        v.total_trials += 1
        v.sound_target = choice(v.spk_freqs)
        if v.sound_target < 5000:
            v.led_target = v.leds[0]
        else:
            v.led_target = v.leds[1]
        hw.light.cue(v.led_target)
        hw.speaker.sine(v.sound_target)
        print("frequency {}".format(v.sound_target))
        set_timer('stimulus_timer', v.stimulus_duration)
    elif event == 'lick':
        goto_state('reward')
    elif event == 'timeout_timer':
        goto_state('timeout')
    elif event == 'stimulus_timer':
        hw.speaker.off()
        hw.light.all_off()
        goto_state('intertrial')
        
def reward(event):
    if event == 'entry':
        hw.reward.release()
        v.correct_trials += 1
        print('reward number {}/{} ({})'.format(v.correct_trials, v.total_trials, v.sound_target))
        timed_goto_state('intertrial', 1000)
        reset_timer('timeout_timer',v.target_duration)
        
def timeout(event):
    "timeout state"
    if event == 'entry':
        hw.speaker.off()
        hw.light.all_off()
        timed_goto_state('intertrial', v.timeout_duration)
    elif event == 'exit':
        reset_timer('timeout_timer',v.target_duration)
 
def all_states(event):
    if event == 'session_timer':
        stop_framework()
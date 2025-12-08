###############################################################################
# Operant lick task (Stimulus -> Lick -> Reward)                              #
###############################################################################
from pyControl.utility import *
import hardware_definition as hw
from devices import *
import utime
import random

# -------------------------------------------------------------------------
#  States and events
# -------------------------------------------------------------------------
states = ['trial',
          'reward',
          'intertrial']

events = ['lick',
          'session_timer',
          'stim_timer',
          'response_timer',
          'motion']

initial_state = 'trial'

# -------------------------------------------------------------------------
#  Task variables
# -------------------------------------------------------------------------
v.session_duration = 30 * minute
v.reward_duration = 35 * ms
v.reward_number = 0

v.trial_len = 3 * second      # Duration of intertrial interval (base)
v.pre_stim_len = 0 * second # Delay before stimulus onset in trial
v.response_window = 3 * second # Time to lick before miss

v.led_direction = 100         # Direction for LED cue (0-100)
v.go_stim_freq = 10000       # Frequency for Go tone

# -------------------------------------------------------------------------
#  Framework hooks
# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    hw.light.start()
    hw.speaker.set_volume(10) # Ensure speaker volume is set
    utime.sleep_ms(20)
    hw.light.all_red()
    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

def run_end():
    "Code here is executed when the framework stops running."
    hw.light.all_off()
    hw.light.off()
    hw.speaker.off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.off()

# -------------------------------------------------------------------------
#  States
# -------------------------------------------------------------------------
def trial(event):
    "Stimulus presentation state."
    if event == 'entry':
        hw.light.all_red() # Ensure Red at start of trial
        set_timer('stim_timer', v.pre_stim_len)
    
    elif event == 'stim_timer':
        # Turn on Sound and LED
        hw.light.cue(v.led_direction) 
        hw.speaker.sine(v.go_stim_freq)
        print('{}, stimulus_on'.format(get_current_time()))
        set_timer('response_timer', v.response_window)

    elif event == 'lick':
        # Check if stimulus is on? 
        # User said "after some time... if lick is detected".
        # If they lick BEFORE stim, it might be premature.
        # But for simplicity, I'll allow it or wait for stim?
        # "if lick is detected, the reward is released" usually implies AFTER stim.
        # I will check if timer 'response_timer' is active (meaning stim is on).
        goto_state('reward')
 

    elif event == 'response_timer':
        # Miss
        print('{}, miss'.format(get_current_time()))
        goto_state('intertrial')

def reward(event):
    "Reward state."
    if event == 'entry':
        hw.speaker.off() # Turn off sound
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        timed_goto_state('intertrial',0.5*second)

def intertrial(event):
    "Intertrial interval."
    if event == 'entry':
        hw.speaker.off()
        hw.light.all_red() # Back to Red background
        timed_goto_state('trial', v.trial_len)

def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'session_timer':
        stop_framework()

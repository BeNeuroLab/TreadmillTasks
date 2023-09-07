# PyTreadmillTask

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial_start',
          'led_on',
          'disengaged',
          'reward',
          'penalty']

events = ['lick',
          'session_timer',
          'led_timer',
          'motion']

initial_state = 'trial_start'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 45 * minute
v.reward_duration = 30 * ms
v.trial_number = 0
v.lick_n___ = 0
v.stim_dir = None
v.max_gap_duration = 10 * second
v.max_IT_duration = 10 * second
v.max_led_duration = 3 * second

# -------------------------------------------------------------------------
# State-independent Code
# -------------------------------------------------------------------------


def cue_random_led(LedDevice: LEDStim):
    """
    Cues 1 LED at a random direction
    """
    stim_dir = randint(0, LedDevice.n_directions - 1)
    LedDevice.all_off()
    LedDevice.cue_led(stim_dir)
    print('{}, LED_direction'.format(stim_dir))

    return stim_dir


# -------------------------------------------------------------------------
# Define behaviour.
# -------------------------------------------------------------------------


# Run start and stop behaviour.
def run_start():
    "Code here is executed when the framework starts running."
    set_timer('session_timer', v.session_duration, True)
    hw.motionSensor.record()
    hw.LED_Delivery.all_off()
    print('CPI={}'.format(hw.motionSensor.sensor_x.CPI))
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.threshold = 10
    hw.speaker.set_volume(50)
    hw.speaker.noise(20000)

def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.LED_Delivery.all_off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.speaker.off()
    hw.off()

# State behaviour functions.

def trial_start(event):
    "beginning of the trial"
    if event == 'entry':
        v.stim_dir = None  # reset stim_dir, otherwise any lick will be rewarded, even before LED presentation
        hw.speaker.noise(20000)
        timed_goto_state('disengaged', v.max_IT_duration)
    if event == 'motion' or event == 'lick':  # any action will start the trial
        goto_state('led_on')

def led_on(event):
    "turn on the led"
    if event == 'entry':
        v.lick_n___ = 0
        hw.LED_Delivery.cue_led(2)
        set_timer('led_timer', v.max_led_duration, False)
    if event == 'exit':
        hw.LED_Delivery.all_off()
        disarm_timer('led_timer')
    elif event == 'led_timer':
        goto_state('penalty')
    elif event == 'lick':
        if v.lick_n___ == 2:  # ignore the first lick, might be a false positive
            t_rem = timer_remaining('led_timer')
            if t_rem < v.max_led_duration - 1000:
                goto_state('reward') 
            else:
                timed_goto_state('reward', 1000 + t_rem - v.max_led_duration)

def disengaged(event):
    "disengaged state"
    if event == 'entry':
        hw.LED_Delivery.all_off()
        hw.speaker.off()
    elif event =='motion':
        goto_state('trial_start')

def penalty(event):
    "penalty state"
    if event == 'entry':
        hw.LED_Delivery.all_off()
        hw.speaker.set_volume(50)
        hw.speaker.sine(10000)
        timed_goto_state('trial_start', randint(v.max_led_duration, v.max_IT_duration))

def reward(event):
    "reward state"
    if event == 'entry':
        hw.LED_Delivery.all_off()
        hw.reward.release()
        v.trial_number += 1
        print('{}, trial_number'.format(v.trial_number))
        timed_goto_state('trial_start', randint(1, v.max_gap_duration))

# State independent behaviour.
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    Executes before the state code.
    """
    if event == 'lick':
        v.lick_n___ += 1
    elif event == 'session_timer':
        hw.motionSensor.stop()
        stop_framework()

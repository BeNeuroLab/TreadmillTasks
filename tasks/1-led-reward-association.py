# PyTreadmillTask

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial',
          'led_on',
          'disengaged',
          'gap']

events = ['lick',
          'session_timer',
          'motion']

initial_state = 'trial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 45 * minute
v.reward_duration = 30 * ms
v.reward_number = 0
v.stim_dir = None
v.n_lick___ = 5
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
    hw.cameraTrigger.start()
    hw.motionSensor.record()
    hw.led.all_off()
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.threshold = 10
    hw.audio.set_volume(20)

def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.led.all_off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.cameraTrigger.stop()
    hw.audio.all_off()
    hw.audio.stop()
    hw.off()

# State behaviour functions.

def trial(event):
    "beginning of the trial"
    if event == 'entry':
        v.stim_dir = None  # reset stim_dir, otherwise any lick will be rewarded, even before LED presentation
        hw.audio.cue(3)
        timed_goto_state('disengaged', v.max_IT_duration)
    elif event == 'motion' or event == 'lick':  # any action will start the trial
        goto_state('led_on')

def led_on(event):
    "turn on the led"
    if event == 'entry':
        hw.led.cue_led(2)
        timed_goto_state('gap', v.max_led_duration)
        if v.n_lick___ >= 3:
            hw.reward.release()
            v.n_lick___ = 0
            v.reward_number += 1
            print('{}, reward_number'.format(v.reward_number))
    elif event == 'exit':
        hw.led.all_off()

def disengaged(event):
    "disengaged state"
    if event == 'entry':
        hw.led.all_off()
    elif event =='motion' or event == 'lick':
        goto_state('led_on')

def gap(event):
    "penalty state"
    if event == 'entry':
        hw.led.all_off()
        timed_goto_state('trial', randint(v.max_led_duration, v.max_IT_duration))


# State independent behaviour.
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    Executes before the state code.
    """
    if event == "lick":
        v.n_lick___ += 1
    elif event == 'session_timer':
        hw.motionSensor.stop()
        stop_framework()

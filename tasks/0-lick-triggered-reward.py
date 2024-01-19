# PyTreadmillTask

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['intertrial',
          'trial',
          'led_on']

events = ['lick',
          'motion',
          'session_timer']

initial_state = 'trial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 20 * minute
v.reward_duration = 50 * ms
v.trial_number = 0

# intertrial params
v.min_IT_movement___ = 10  # cm - must be a multiple of 5
v.x___ = 0
v.y___ = 0

# trial params
v.trial_len = 3 * second
v.led_len = 500 * ms



# -------------------------------------------------------------------------
# Define behaviour.
# -------------------------------------------------------------------------


# Run start and stop behaviour.
def run_start():
    "Code here is executed when the framework starts running."
    set_timer('session_timer', v.session_duration, True)
    hw.audio.start()
    hw.motionSensor.record()
    hw.cameraTrigger.start()
    hw.LED_Delivery.all_off()
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.threshold = v.min_IT_movement___

def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.LED_Delivery.all_off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.audio.stop()
    hw.off()

# State behaviour functions.
def trial(event):
    "start state behaviour"
    if event == 'entry':
        hw.audio.cue(3)
    if event == 'lick':
        goto_state('led_on')

def led_on(event):
    "gap for the LED cue"
    if event == 'entry':
        hw.audio.all_off()
        hw.LED_Delivery.cue_led(2)
        hw.reward.release()
        timed_goto_state('intertrial', v.led_len)  # half a seconf of LED cue

def intertrial(event):
    "intertrial"
    if event == 'entry':
        hw.LED_Delivery.all_off()
        v.trial_number += 1

        print('{}, reward_number'.format(v.trial_number))
        timed_goto_state('trial', v.trial_len)  # enforcing min 1s between rewards

# State independent behaviour.
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    """
    if event == 'session_timer':
        stop_framework()

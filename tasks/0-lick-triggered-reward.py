# PyTreadmillTask

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['intertrial',
          'trial_start',
          'cue_gap']

events = ['lick',
          'motion',
          'session_timer']

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 30 * minute
v.reward_duration = 70 * ms
v.trial_number = 0

# intertrial params
v.min_IT_movement = 5  # cm - must be a multiple of 5
v.x___ = 0
v.y___ = 0

# trial params
v.trial_len = 3 * second
v.led_len = 500 * ms



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


def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.LED_Delivery.all_off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.off()

# State behaviour functions.
def intertrial(event):
    "intertrial state behaviour"
    if event == 'entry':
        # coded so that at this point, there is clean air coming from every direction
        hw.motionSensor.threshold = v.min_IT_movement # to issue an event only after enough movement
    elif event == 'lick':
        hw.reward.release()
        cue_random_led(hw.LED_Delivery)
        goto_state('cue_gap')

def cue_gap(event):
    "gap for the LED cue"
    if event == 'entry':
        timed_goto_state('trial_start', v.led_len)  # half a seconf of LED cue

def trial_start(event):
    "beginning of the trial"
    if event == 'entry':
        hw.LED_Delivery.all_off()
        v.trial_number += 1
        print('{}, trial_number'.format(v.trial_number))
        timed_goto_state('intertrial', v.trial_len)  # enforcing min 1s between rewards

# State independent behaviour.
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    """
    if event == 'session_timer':
        hw.motionSensor.stop()
        stop_framework()

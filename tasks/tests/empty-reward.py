# PyTreadmillTask

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['intertrial']

events = ['lick',
          'session_timer',
          'motion']

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 30 * minute
v.reward_duration = 1000 * ms
v.trial_number = 0

# intertrial params
v.min_IT_movement = 5  # cm - must be a multiple of 5
v.x___ = 0
v.y___ = 0

# trial params
v.trial_len = 1 * ms
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
    LedDevice.cue(stim_dir)
    print('{}, LED_direction'.format(stim_dir))

    return stim_dir

# -------------------------------------------------------------------------
# Define behaviour.
# -------------------------------------------------------------------------


# Run start and stop behaviour.
def run_start():
    "Code here is executed when the framework starts running."
    set_timer('session_timer', v.session_duration, True)
    hw.reward.sol.on()    

def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.light.all_off()
    hw.reward.sol.off()
    hw.motionSensor.off()
    hw.off()

# State behaviour functions.
def intertrial(event):
    "intertrial state behaviour"
    hw.light.all_on()

# State independent behaviour.
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    """
    if event == 'session_timer':
        hw.motionSensor.stop()
        stop_framework()

# PyTreadmillTask

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math
import uarray

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['intertrial']

events = ['motion','timer',
          'session_timer']

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# session params
v.session_duration = 30 * minute


# Run start and stop behaviour.
def run_start():
    # Code here is executed when the framework starts running.
    set_timer('session_timer', v.session_duration, True)
    hw.motionSensor.record()
    hw.cameraTrigger.start()
    print('internal th={}'.format(hw.motionSensor._threshold))
    print('external th={}'.format(hw.motionSensor.threshold))
    print('CPI={}'.format(hw.motionSensor.sensor_x.CPI))
    hw.audio.set_volume(29)
def run_end():
    # Code here is executed when the framework stops running.
    # Turn off all hardware outputs.
    hw.motionSensor.off()
    hw.off()


# State behaviour functions.
def intertrial(event):
    # hw.LED_Delivery.all_off()
    set_timer('timer', 5 * second, True)


# State independent behaviour.
def all_states(event):
    # Code here will be executed when any event occurs,
    # irrespective of the state the machine is in.
    if event == 'motion':
        # read the motion registers and and append the variables
        print('dX={}; dY={}'.format(hw.motionSensor.x / hw.motionSensor.sensor_x.CPI * 2.54, hw.motionSensor.y / hw.motionSensor.sensor_x.CPI * 2.54))
    elif event == 'timer':
            hw.audio.set_volume(0)
            set_timer('timer', 5 * second, True)
    elif event == 'session_timer':
        hw.motionSensor.stop()
        stop_framework()

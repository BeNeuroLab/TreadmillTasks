from pyControl.utility import *
import hardware_definition as hw
from random import randrange, uniform

from devices import *
from random import randint
import time  # Import the time library

# States and events
states = [
    'free',
    'intertrial',
    'trial',
]
events = [
    'sol_on',
    'sol_off',
    'session_timer',
    'trial_timer',
    'session_timer',
    'motion'
]
initial_state = 'free'


# Variables
v.min_motion = 10
v.session_duration = 30 * minute
v.free_duration = 10 * second
v.sol_number = 0
v.sol_duration = 50 * ms
v.trial_duration = 10 * second
v.intertrial_duration = 10 * second
v.trial_limits = (2, 8)


# States
def trial(event):
    if event == 'entry':
        set_timer('trial_timer', v.trial_duration, False)
        set_timer('sol_on', uniform(v.trial_limits[0], v.trial_limits[1]) * second, True)

    elif event == 'sol_on':
        v.sol_number = randrange(11)
        hw.earthquake_stim.sol_on(v.sol_number)
        print('{}, Sol_direction'.format(v.sol_number))
        set_timer('sol_off', v.sol_duration, True)

    elif event =='sol_off':
        hw.earthquake_stim.sol_off(v.sol_number)

    elif event == 'trial_timer':
        goto_state('intertrial')



def intertrial(event):
    if event == 'entry':
        timed_goto_state('trial', v.intertrial_duration)


def free(event):
    if event == 'entry':
        timed_goto_state('intertrial', v.free_duration)


# State independent functions
def all_states(event):
    if event == 'session_timer':
        stop_framework()


def run_start():
    """
    Code here is executed when the framework starts running.
    """
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.min_motion
    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    # print('{}, before_camera_trigger'.format(get_current_time()))
    # hw.cameraTrigger.start()


def run_end():
    """
    Code here is executed when the framework stops running
    """
    hw.motionSensor.stop()
    # hw.cameraTrigger.stop()
    hw.off()

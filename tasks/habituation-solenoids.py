from pyControl.utility import *
import hardware_definition as hw

from devices import *
from random import randint
import time  # Import the time library

earthquake_stim = shakeStim(port_exp=Port_expander(port=hw.board.port_8))

# States and events
states = [
    'free',
    'intertrial',
    'trial',
]
events = [
    'session_timer',
    'intertrial_timer',
    'trial_timer',
    'session_timer',
    'motion'
]
initial_state = 'free'


# Variables
v.min_motion = 10
v.session_duration = 10 * minute
v.free_duration = 5 * minute
v.sol_number = 0
v.trial_duration = 10 * second
v.trial_min_period = 2 * second
v.intertrial_duration = 10 * second


# States
def trial(event):
    if event == 'entry':
        set_timer('trial_timer', v.trial_duration, True)
        set_timer('sol_onset', random.uniform(v.trial_min_period, ))

    elif event == 'trial_timer':
        goto_state('intertrial')


def intertrial(event):
    if event == 'entry':
        set_timer('intertrial_timer', v.intertrial_duration, True)

    elif event == 'intertrial_timer':
        goto_state('trial')


def free(event):
    if event == 'entry':
        timed_goto_state('intertrial', v.free_duration, True)

def all_states(event):
    if event == 'session_timer':
        stop_framework()

# Common functions
def run_start():
    """
    Code here is executed when the framework starts running.
    """
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.min_motion
    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()


def run_end():
    """
    Code here is executed when the framework stops running
    """
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.off()

from pyControl.utility import *
import hardware_definition as hw
from random import randrange, uniform, choice

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
    'motion',
    'earthquake_duration',
    'free_duration'
]
initial_state = 'free'


# Variables
v.min_motion = 10
v.session_duration = 89 * minute
v.free_duration = 10 * minute
v.earthquake_duration = 70 * minute
v.sol_number = 0
v.sol_off_time_list = [50, 100, 150]
v.sol_off_time = 0
v.trial_duration = 4 * second
v.intertrial_duration = [1, 3, 5, 7]
v.sol_onset_time = 2 * second


# States
def trial(event):
    if event == 'entry':
        set_timer('trial_timer', v.trial_duration, False)
        set_timer('sol_on', v.sol_onset_time, True)
        v.sol_number = randrange(11)
        v.sol_off_time = choice(v.sol_off_time_list)
        print('{}, Sol_direction'.format(v.sol_number))
        print('{}, Sol_duration'.format(v.sol_off_time))


    elif event == 'sol_on':
        hw.earthquake_stim.sol_on(v.sol_number)
        set_timer('sol_off', v.sol_off_time * ms, False)

    elif event =='sol_off':
        hw.earthquake_stim.sol_off(v.sol_number)

    elif event == 'trial_timer':
        goto_state('intertrial')



def intertrial(event):
    if event == 'entry':
        timed_goto_state('trial', choice(v.intertrial_duration) * second)


def free(event):
    if event == 'entry':
        set_timer('free_duration', v.free_duration, False)

    elif event == 'free_duration':
        set_timer('earthquake_duration', v.earthquake_duration, True)
        goto_state('intertrial')



# State independent functions
def all_states(event):
    if event == 'earthquake_duration':
        goto_state('free')
    elif event == 'session_timer':
        stop_framework()


def run_start():
    """
    Code here is executed when the framework starts running.
    """
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.min_motion
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))

    set_timer('session_timer', v.session_duration, True)

    hw.earthquake_stim.kill_switch.on()

    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()


def run_end():
    """
    Code here is executed when the framework stops running
    """
    hw.motionSensor.stop()
    hw.earthquake_stim.kill_switch.off()
    hw.cameraTrigger.stop()
    hw.off()

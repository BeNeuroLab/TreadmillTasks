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
v.session_duration = 1.25 * minute
v.free_duration = 10 * second
v.earthquake_duration = 1 * minute

v.num_of_solenoids_to_flurry = 6
v.sols_to_flurry = set()
v.solenoids = list(range(11))
v.sol_idx = 0

v.sol_off_time = 50 * ms
v.trial_duration = 4 * second
v.intertrial_duration = [1, 3, 5, 10]
v.flurry_onset = 2 * second


# States
def trial(event):
    if event == 'entry':
        set_timer('trial_timer', v.trial_duration, False)
        set_timer('sol_on', v.flurry_onset, True)

        v.sol_idx = 0
        v.sols_to_flurry = set()
        while len(v.sols_to_flurry) < v.num_of_solenoids_to_flurry:
            v.sols_to_flurry.add(choice(v.solenoids))

        v.sols_to_flurry = list(v.sols_to_flurry)
        print('{}, Sol_flurry'.format(v.sols_to_flurry))
        
    elif event == 'sol_on':
        hw.earthquake_stim.sol_on(v.sols_to_flurry[v.sol_idx])
        set_timer('sol_off', v.sol_off_time, False)

    elif event == 'sol_off':
        hw.earthquake_stim.sol_off(v.sols_to_flurry[v.sol_idx])
        v.sol_idx = v.sol_idx + 1
        if v.sol_idx < v.num_of_solenoids_to_flurry:
            set_timer('sol_on', 0 * ms, True)

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

    # hw.cameraTrigger.stop()
    hw.off()

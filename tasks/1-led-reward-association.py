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
          'stim_on',
          'reward']

events = ['motion',
          'lick',
          'session_timer',
          'IT_timer',
          'stim_timer']

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 60 * minute
v.reward_duration = 50 * ms
v.stim_duration = 1 * second

v.trial_number = 0

# intertrial params
v.min_IT_movement = 5  # cm - must be a multiple of 5
v.min_IT_duration = 2 * second
v.IT_duration_done___ = False
v.IT_distance_done___ = False
v.x___ = 0
v.y___ = 0

# trial params
v.led_direction = -1
v.trial_start_len = 100 * ms

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
    assert v.stim_duration < v.min_IT_duration

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
        set_timer('IT_timer', v.min_IT_duration)
        v.IT_duration_done___ = False
        v.IT_distance_done___ = False
        hw.motionSensor.threshold = v.min_IT_movement # to issue an event only after enough movement
    elif event == 'exit':
        disarm_timer('IT_timer')
    elif event == 'IT_timer':
        v.IT_duration_done___ = True
        if v.IT_distance_done___:
            goto_state('trial_start')
    elif event == 'motion':
        v.IT_distance_done___ = True
        if v.IT_duration_done___:
            goto_state('trial_start')


def trial_start(event):
    "beginning of the trial"
    if event == 'entry':
        v.trial_number += 1
        print('{}, trial_number'.format(v.trial_number))
        v.led_direction = cue_random_led(hw.LED_Delivery)
        set_timer('stim_timer', v.stim_duration, False)
        timed_goto_state('reward', v.trial_start_len)



def reward(event):
    "reward state"
    if event == 'entry':
        timed_goto_state('intertrial', v.min_IT_duration)
    elif event == 'lick' or event == 'lick_off':  # any lick-related event during reward
        hw.reward.release()
        goto_state('intertrial')


# State independent behaviour.
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    """
    if event == 'motion':
        # read the motion registers
        # to convert to cm, divide by CPI and multiply by 2.54
        v.x___ = hw.motionSensor.x #/ hw.motionSensor.sensor_x.CPI * 2.54
        v.y___ = hw.motionSensor.y #/ hw.motionSensor.sensor_x.CPI * 2.54
        print('{},{}, dM'.format(v.x___, v.y___))
    elif event == 'stim_timer':
        hw.LED_Delivery.all_off()

    elif event == 'session_timer':
        hw.motionSensor.stop()
        stop_framework()

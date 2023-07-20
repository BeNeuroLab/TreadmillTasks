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

events = ['lick',
          'lick_off',
          'session_timer',
          'reward_timer']

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 45 * minute
v.reward_duration = 70 * ms
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
v.trial_start_len = 1 * second


# -------------------------------------------------------------------------
# Define behaviour.
# -------------------------------------------------------------------------


# Run start and stop behaviour.
def run_start():
    "Code here is executed when the framework starts running."
    set_timer('session_timer', v.session_duration, True)
    hw.motionSensor.record()
    print('CPI={}'.format(hw.motionSensor.sensor_x.CPI))


def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.LED_Delivery.all_off()
    hw.rewardSol.off()
    hw.motionSensor.off()
    hw.off()

# State behaviour functions.
def intertrial(event):
    "intertrial state behaviour"
    if event == 'entry':
        # coded so that at this point, there is clean air coming from every direction
        hw.motionSensor.threshold = v.min_IT_movement # to issue an event only after enough movement
    elif event == 'lick':
        goto_state('reward')


def trial_start(event):
    "beginning of the trial"
    if event == 'entry':
        v.trial_number += 1
        print('{}, trial_number'.format(v.trial_number))
        hw.LED_Delivery.all_off()
        timed_goto_state('intertrial', v.trial_start_len)  # enforcing min 1s between rewards


def reward(event):
    "reward state"
    if event == 'entry':
        set_timer('reward_timer', v.reward_duration, False)
        hw.rewardSol.on()
        print('{}, reward_on'.format(get_current_time()))
    elif event == 'exit':
        disarm_timer('reward_timer')
    elif event == 'reward_timer':
        hw.rewardSol.off()
        goto_state('trial_start')


# State independent behaviour.
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    """
    if event == 'session_timer':
        hw.motionSensor.stop()
        stop_framework()

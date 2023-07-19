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
          'lick_off',
          'session_timer',
          'IT_timer',
          'max_IT_timer',
          'stim_timer',
          'reward_timer',
          ]

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 15 * minute
v.reward_duration = 100 * ms
v.trial_number = 0

# intertrial params
v.min_IT_movement = 5  # cm - must be a multiple of 5
v.min_IT_duration = 1 * second
v.max_IT_duration = 10 * second
v.IT_duration_done___ = False
v.IT_distance_done___ = False
v.x___ = 0
v.y___ = 0

# trial params
v.stim_len = 10 * second
v.distance_to_target = 5  # cm - must be a multiple of 5
v.target_angle_tolerance = math.pi / 18  # deg_rad
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
    set_timer('session_timer', v.session_duration, True)
    hw.motionSensor.record()
    hw.LED_Delivery.all_off()
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
        set_timer('IT_timer', v.min_IT_duration)
        hw.LED_Delivery.all_off()
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
        hw.LED_Delivery.all_off()
        timed_goto_state('reward', v.trial_start_len)



def reward(event):
    "reward state"
    if event == 'entry':
        v.led_direction = cue_random_led(hw.LED_Delivery)
        set_timer('reward_timer', v.reward_duration, False)
        hw.rewardSol.on()
        print('{}, reward_on'.format(get_current_time()))
    elif event == 'exit':
        disarm_timer('reward_timer')
    elif event == 'reward_timer':
        hw.rewardSol.off()
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
    elif event == 'lick':
        #TODO: handle the lick data better
        pass
    elif event == 'session_timer':
        hw.motionSensor.stop()
        stop_framework()

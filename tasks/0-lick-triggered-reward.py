# PyTreadmillTask

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math


# -------------------------------------------------------------------------
states = ['intertrial',
          'trial',
          'reward']

events = ['lick',
          'session_timer',
          'motion']

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 20 * minute
v.reward_duration = 30 * ms
v.trial_number = 0

# intertrial params
v.min_IT_movement___ = 10  # cm - must be a multiple of 5
v.x___ = 0
v.y___ = 0

# trial params
v.trial_len = 5 * second
v.led_len = 500 * ms


# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.sound.set_volume(15)  # Between 1 - 30
    utime.sleep_ms(20)  # wait for the audio player to be ready
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.min_IT_movement___
    hw.sound.start()
    hw.light.all_off()
    hw.reward.reward_duration = v.reward_duration
    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.light.all_off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.sound.stop()
    hw.off()


# -------------------------------------------------------------------------
def trial(event):
    "start state behaviour"
    if event == 'entry':
        hw.light.cue(3)
    if event == 'lick':
        hw.sound.cue(3)
        timed_goto_state('reward', v.led_len)

def reward(event):
    "gap for the light cue"
    if event == 'entry':
        hw.reward.release()
        print('{}, reward_number'.format(v.trial_number))
        timed_goto_state('intertrial', v.led_len)

def intertrial(event):
    "intertrial"
    if event == 'entry':
        hw.light.all_off()
        hw.sound.all_off()
        v.trial_number += 1
        timed_goto_state('trial', v.trial_len)  # enforcing min 3s between rewards


def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'session_timer':
        stop_framework()

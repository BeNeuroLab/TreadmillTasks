"lick -> reward -> intertrial"

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import utime


# -------------------------------------------------------------------------
states = ['trial',
          'intertrial',
          'reward']

events = ['lick',
          'session_timer',
          'motion']

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 5 * minute
v.reward_duration = 40 * ms
v.reward_number = 0

v.trial_len = 3 * second


# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.threshold = 5
    hw.motionSensor.record()
    hw.speaker.set_volume(10)
    hw.light.start()
    hw.light.off()
    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    print('{}, before_camera_trigger'.format(get_current_time()))
    print('{}, acquiring'.format(int(hw.motionSensor.acquiring)))
    print('{}, sampling_rate'.format(hw.motionSensor.data_chx.sampling_rate))
    hw.cameraTrigger.start()

def run_end():
    "Code here is executed when the framework stops running."
    hw.light.off()
    hw.speaker.off()
    hw.reward.stop()
    hw.motionSensor.stop()
    hw.motionSensor.off()
    hw.cameraTrigger.stop()
    hw.off()

# -------------------------------------------------------------------------
def trial(event):
    "led at first, and spk update at later bins"
    if event == 'entry':
        hw.light.off()
    elif event == 'lick':  
        goto_state('reward')

def reward (event):
    "reward state"
    if event == 'entry':
        timed_goto_state('trial', v.trial_len)
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))


def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'session_timer':
        stop_framework()

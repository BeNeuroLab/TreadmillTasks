"lick -> light on -> reward -> intertrial"

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
v.session_duration = 30 * minute
v.reward_duration = 50 * ms
v.reward_number = 0

v.trial_len = 3 * second
v.led_len = 500 * ms

v.spks___ = [3]
v.leds___ = [3]


# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.sound.set_volume(5)  # Between 1 - 30
    utime.sleep_ms(20)  # wait for the sound player to be ready
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    hw.sound.start()
    hw.light.all_off()
    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

def run_end():
    "Code here is executed when the framework stops running."
    hw.light.all_off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.sound.stop()
    hw.off()


# -------------------------------------------------------------------------
def trial(event):
    "led at first, and spk update at later bins"
    if event == 'entry':
        hw.light.all_off()
        hw.sound.all_off()
    elif event == 'lick':  # lick during the trial delays the sweep
        hw.light.cue(v.leds___[0])
        print('{}, led_direction'.format(hw.light.active[0]))
        hw.sound.cue(v.spks___[0])
        print('{}, spk_direction'.format(hw.sound.active[0]))
        timed_goto_state('reward', v.led_len)

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

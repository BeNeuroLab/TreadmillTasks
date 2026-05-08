"lick -> light on -> reward -> intertrial"

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import utime


# -------------------------------------------------------------------------
states = ['trial',
    'intertrial',
    'reward'
]

events = ['lick',
    'session_timer',
    'motion'
]

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 30 * minute
v.reward_duration = 35 * ms
v.reward_number = 0

v.trial_len = 1 * second
v.led_len = 300 * ms

v.leds___ = [100]


# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    hw.light.start()
    utime.sleep_ms(20)  # wait for the light
    hw.light.all_red()
    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

def run_end():
    "Code here is executed when the framework stops running."
    hw.light.all_off()
    hw.light.off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.off()


# -------------------------------------------------------------------------
def trial(event):
    "led at first, and spk update at later bins"
    if event == 'entry':
        hw.light.all_red()
    elif event == 'lick':  # lick during the trial delays the sweep
        hw.light.cue(v.leds___[0])
        print('{}, led_direction'.format(v.leds___[0]))
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

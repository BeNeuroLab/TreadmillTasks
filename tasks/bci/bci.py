"1-stim-triggered-reward.py"

import utime
from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial',
          'stim_match',
          'reward']

events = ['lick',
          'motion',
          'bci_update',
          'session_timer']

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 60 * minute
v.reward_duration = 30 * ms
v.hold_duration = 200 * ms

v.reward_number = 0
v.IT_duration = 5 * second

v.spks___ = [0, 1, 2, 3, 4, 5, 6]
v.leds___ = [1, 2, 3, 4, 5]
v.next_led___ = v.leds___[-1]


# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.sound.set_volume(8)  # Between 1 - 30
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
    "Trial state"
    if event == 'entry':
        hw.light.cue(v.next_led___)
        print('{}, led_direction'.format(v.next_led___))
    elif event == 'bci_update':
        if hw.light.active[0] in hw.sound.active:
            goto_state('stim_match')

def stim_match (event):
    "reward state"
    if event == 'entry':
        timed_goto_state('reward', v.hold_duration)
    elif event == 'bci_update':
        goto_state('trial')

def reward (event):
    "intertrial state"
    if event == 'entry':
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        hw.light.all_off()
        timed_goto_state('trial', v.IT_duration)
        v.next_led___ = choice(v.leds___)


def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'bci_update':
        spk_dir = hw.bci_link.spk
        print('{}, spk_direction'.format(spk_dir))
        hw.sound.cue(spk_dir)
    elif event == 'session_timer':
        stop_framework()

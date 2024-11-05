"""task with 2 LEDs only and a penalty for offlicks (no timeout)
"""

import utime
from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial',
          'cursor_match',
          'reward',
          'penalty']

events = ['lick',
          'motion',
          'session_timer']

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 45 * minute
v.reward_duration = 30 * ms

v.sound_bins = (0.75 * second, 1 * second, 2 * second)

v.reward_number = 0
v.IT_duration = 5 * second


v.spks___ = [3]
v.leds___ = [3]
v.next_led___ = v.leds___[-1]


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
    "trial"
    if event == 'entry':
        hw.light.all_off()
        hw.sound.all_off()
        timed_goto_state('cursor_match', choice(v.sound_bins))
    elif event == 'lick':
        goto_state('penalty')

def cursor_match (event):
    "when led and spk line up"
    if event == 'entry':
        hw.sound.cue(v.spks___[0])
        print('{}, spk_direction'.format(hw.sound.active[0]))
        hw.light.cue(v.leds___[0])
        print('{}, led_direction'.format(hw.light.active[0]))
        timed_goto_state('trial', v.sound_bins[-1])
    elif event == 'lick':
        goto_state('reward')

def reward (event):
    "reward state"
    if event == 'entry':
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        timed_goto_state('trial', v.IT_duration)

def penalty (event):
    "penalty state"
    if event == 'entry':
        timed_goto_state('trial', v.sound_bins[-1])
    elif event == 'lick':
        goto_state('penalty')


def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'session_timer':
        stop_framework()

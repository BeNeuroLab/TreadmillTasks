"""task with 2 LEDs only and a penalty for offlicks (no timeout)
"""

import utime
from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = [
    'trial',
    'cursor_match',
    'reward'
]

events = [
    'lick',
    'motion',
    'session_timer'
]

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 30 * minute
v.reward_duration = 35 * ms

v.sweep_bins = (.1 * second, .2 * second, .5 * second)
v.cursor_match_dur = .5 * second

v.reward_number = 0
v.IT_duration = 5 * second


v.leds___ = list(range(1,101))
v.current_led___ = v.leds___[0]
v.next_led___ = v.leds___[0]

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
    "trial"
    if event == 'entry':
        hw.light.cue(v.next_led___)
        print('{}, led_direction'.format(v.next_led___))
        v.current_led___ = v.next_led___
        v.next_led___ += 2
        if v.next_led___ < v.leds___[-1]:
            timed_goto_state('trial', choice(v.sweep_bins))
        else:
            timed_goto_state('cursor_match', choice(v.sweep_bins))

def cursor_match(event):
    "when led is at the target"
    if event == 'entry':
        hw.light.cue(v.leds___[-1])
        print('{}, led_direction'.format(v.leds___[-1]))
        v.next_led___ = 1
        timed_goto_state('trial', v.cursor_match_dur)
    elif event == 'lick':
        goto_state('reward')

def reward(event):
    "reward state"
    if event == 'entry':
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        v.next_led___ = 1
        timed_goto_state('trial', v.IT_duration)

def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'session_timer':
        stop_framework()

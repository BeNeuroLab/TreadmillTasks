"""task with all LEDs and a penalty for offlicks (no timeout)
penalty is cursor reset to spk 0 and wait for v.IT_duration=5s from the last offlick
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
          'cursor_update',
          'session_timer']

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 60 * minute
v.reward_duration = 30 * ms
v.sound_bins = (0.5 * second, 0.75 * second, 1 * second, 3 * second)

v.reward_number = 0
v.IT_duration = 5 * second

v.last_spk___ = 1
v.next_spk___ = 0

v.spks___ = [0, 1, 2, 3, 4, 5, 6]
v.leds___ = [1, 2, 3, 4, 5]
v.next_led___ = v.leds___[-1]


# -------------------------------------------------------------------------
def next_spk():
    """
    returns the next speakers, in either direction of the sweep
    """
    assert len(hw.sound.active)==1, 'one speaker can be active'
    active_spk = hw.sound.active[0]
    active_spk_idx = v.spks___.index(active_spk)

    if active_spk > v.last_spk___:
        if active_spk < v.spks___[-1]:
            out = active_spk_idx + 1
        else:
            out = active_spk_idx - 1
    else:
        if active_spk > v.spks___[0]:
            out = active_spk_idx - 1
        else:
            out = active_spk_idx + 1

    v.last_spk___ = active_spk

    return v.spks___[out]


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
    "trial state"
    if event == 'entry':
        hw.light.all_off()
        hw.sound.cue(v.next_spk___)
        print('{}, spk_direction'.format(v.next_spk___))
        set_timer('cursor_update', choice(v.sound_bins), False)
        v.next_led___ = choice(v.leds___)
    elif event == 'lick':  # lick during the trial delays the sweep
        goto_state('penalty')
    elif event == 'cursor_update':
        if hw.sound.active[0] == v.next_led___:
            goto_state('cursor_match')
        else:
            set_timer('cursor_update', choice(v.sound_bins), False)
    elif event == 'exit':
        disarm_timer('cursor_update')

def cursor_match (event):
    "when led and spk line up"
    if event == 'entry':
        hw.light.cue(v.next_led___)
        print('{}, led_direction'.format(v.next_led___))
        timed_goto_state('trial', v.sound_bins[-1])
        v.next_spk___ = next_spk()  # in case of no lick, sweep continues
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
    """
    penalty state
    penalty is cursor reset to spk-0 and wait for v.IT_duration=5s from the last offlick
    """
    if event == 'entry':
        timed_goto_state('trial', v.IT_duration)
        hw.sound.cue(v.spks___[0])
        print('{}, spk_direction'.format(v.spks___[0]))
        v.next_spk___ = next_spk()
    elif event == 'lick':
        goto_state('penalty')  # extend the penalty state


def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'cursor_update':
        spk_dir = next_spk()
        print('{}, spk_direction'.format(spk_dir))
        hw.sound.cue(spk_dir)
    elif event == 'session_timer':
        stop_framework()

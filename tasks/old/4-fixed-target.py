"1-stim-triggered-reward.py"

import utime
from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial',
          'led_on',
          'reward',
          'timeout']

events = ['lick',
          'motion',
          'spk_update',
          'led_timer',
          'session_timer']

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 45 * minute
v.reward_duration = 20 * ms
v.sound_bins = (0.5 * second, 0.6 * second, 0.7 * second, 1.5 * second)
v.offlick_penalty = 5 * second
v.target_duration = 2 * minute
v.timeout_duration = 20 * second

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
    set_timer('led_timer',v.target_duration)

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
        hw.sound.cue(v.next_spk___)
        print('{}, spk_direction'.format(v.next_spk___))
        set_timer('spk_update', choice(v.sound_bins), False)
    elif event == 'lick':  # lick during the trial delays the sweep
        reset_timer('spk_update', v.offlick_penalty)
        reset_timer('led_timer',v.target_duration)
    elif event == 'spk_update':
        if hw.sound.active[0] == v.next_led___:
            goto_state('led_on')
        else:
            set_timer('spk_update', choice(v.sound_bins), False)
    elif event == 'led_timer':
        goto_state('timeout')
    elif event == 'exit':
        disarm_timer('spk_update')

def led_on (event):
    "reward state"
    if event == 'entry':
        hw.light.cue(v.next_led___)
        print('{}, led_direction'.format(v.next_led___))
        pause_timer('led_timer')
        timed_goto_state('trial', v.sound_bins[-1])
        v.next_spk___ = next_spk()  # in case of no lick, sweep continues
    elif event == 'lick':
        goto_state('reward')
    elif event == 'exit':
        unpause_timer('led_timer')

def reward (event):
    "intertrial state"
    if event == 'entry':
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        v.next_led___ = choice(v.leds___)
        reset_timer('led_timer',v.target_duration)
        timed_goto_state('trial', v.IT_duration)

def timeout(event):
    "timeout state"
    if event == 'entry':
        v.next_led___ = choice(v.leds___)
        hw.light.all_off()
        hw.sound.all_off()
        v.next_spk___ = v.spks___[0]
        timed_goto_state('trial', v.timeout_duration)
    elif event == 'exit':
        reset_timer('led_timer',v.target_duration)

def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'spk_update':
        spk_dir = next_spk()
        hw.sound.cue(spk_dir)
        print('{}, spk_direction'.format(spk_dir))
    elif event == 'session_timer':
        stop_framework()

"reward on lick, half of the time, when sound and light match"
from pyControl.utility import *
import hardware_definition as hw
from devices import *
import utime


# -------------------------------------------------------------------------
states = ['trial',
          'reward']

events = ['lick',
          'session_timer',
          'spk_update',
          'motion']

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 30 * minute
v.reward_duration = 30 * ms
v.sound_bins = (0.5 * second, 0.75 * second, 1 * second)
v.reward_number = 0

v.trial_len = 3 * second
v.led_len = 750 * ms

v.last_spk___ = 1
v.next_spk___ = 0

v.spks___ = [1, 2, 3, 4, 5]
v.leds___ = [1, 2, 3, 4, 5]


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
        hw.sound.cue(v.next_spk___)
        print('{}, spk_direction'.format(v.next_spk___))
        set_timer('spk_update', choice(v.sound_bins), False)
    elif event == 'lick':  # lick during the trial delays the sweep
        hw.light.cue(hw.sound.active[0])
        timed_goto_state('reward', v.led_len)
    elif event == 'spk_update':
        set_timer('spk_update', choice(v.sound_bins), False)
    elif event == 'exit':
        disarm_timer('spk_update')

def reward (event):
    "reward state"
    if event == 'entry':
        timed_goto_state('trial', v.trial_len)
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        v.next_spk___ = next_spk()


def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'spk_update':
        spk_dir = next_spk()
        print('{}, spk_direction'.format(spk_dir))
        hw.sound.cue(spk_dir)
    elif event == 'session_timer':
        stop_framework()

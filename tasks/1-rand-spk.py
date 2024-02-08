# 1-led-reward-association: lining speakers with the mid LED and release the reward.

from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial',
          'reward',
          'penalty']

events = ['lick',
          'motion',
          'session_timer',
          'spk_update']

initial_state = 'trial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 45 * minute
v.reward_duration = 30 * ms
v.reward_number = 0
v.last_spk___ = 0
v.next_spk___ = 6
v.next_led___ = 2
v.IT_duration = 5 * second
v.audio_bin = 500 * ms

v.spks___ = sorted(list(hw.audio.speakers.keys()))


# -------------------------------------------------------------------------
# State-independent Code
# -------------------------------------------------------------------------

def next_spk():
    """
    returns the next speakers, in either direction of the sweep
    """
    assert len(hw.audio.active)==1, 'one one speaker can be active'
    active_spk = hw.audio.active[0]

    if active_spk > v.last_spk___:
        out = active_spk + 1 if active_spk < v.spks___[-1] else active_spk - 1
    else:
        out = active_spk - 1 if active_spk > v.spks___[0] else active_spk + 1
    
    v.last_spk___ = active_spk

    return out


# -------------------------------------------------------------------------
# Define behaviour.
# -------------------------------------------------------------------------

# Run start and stop behaviour.
def run_start():
    "Code here is executed when the framework starts running."
    set_timer('session_timer', v.session_duration, True)
    hw.audio.start()
    hw.cameraTrigger.start()
    hw.motionSensor.record()
    hw.visual.all_off()
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.threshold = 10

def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.visual.all_off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.cameraTrigger.stop()
    hw.audio.all_off()
    hw.audio.stop()
    hw.off()

# State behaviour functions.

def trial(event):
    "led at first, and spk update at later bins"
    if event == 'entry':
        hw.visual.cue(v.next_led___)  # choose from led 2 or 4 as the cue
        hw.audio.cue(v.next_spk___)  # start the trial from one of the end speakers
        set_timer('spk_update', v.audio_bin, False)
    elif event == 'spk_update':
        if hw.audio.active == hw.visual.active:  # speaker lines up with LED
            goto_state('reward')
        else:
            set_timer('spk_update', v.audio_bin, False)


def reward (event):
    "reward state"
    if event == 'entry':
        timed_goto_state('trial', v.IT_duration)
        v.next_spk___ = next_spk()  # in case of no lick, sweep continues
        v.next_led___ = hw.visual.active[0]
    elif event == 'lick':
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        goto_state('intertrial')

def intertrial (event):
    "intertrial state"
    if event == 'entry':
        hw.audio.all_off()
        hw.visual.all_off()
        timed_goto_state('trial', v.IT_duration)
        v.next_spk___ = choice([0,6])  # in case of lick, restart sweep
        v.next_led___ = choice([2,4])

# State independent behaviour.
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    Executes before the state code.
    """
    if event == 'spk_update':
        spk_dir = next_spk()
        print('{}, spk_direction'.format(spk_dir))
        hw.audio.cue(spk_dir)
    elif event == 'session_timer':
        stop_framework()

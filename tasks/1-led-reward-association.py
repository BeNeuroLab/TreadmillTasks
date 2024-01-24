# 1-led-reward-association: lining speakers with the mid LED and release the reward.

from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial',
          'rand_spk',
          'reward']

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
v.spk_dir = 0
v.n_lick___ = 5
v.IT_duration = 3 * second
v.audio_bin = 500 * ms


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
    "beginning of the trial"
    if event == 'entry':
        hw.visual.cue(3)
        v.spk_dir = 0
        timed_goto_state('rand_spk', v.audio_bin)

def rand_spk(event):
    "turn on the led"
    if event == 'entry':
        hw.audio.cue(v.spk_dir)
        set_timer('spk_update', v.audio_bin, False)
    elif event == 'spk_update':
        if v.spk_dir == 3:  # speaker lines up with LED
            timed_goto_state('reward', v.audio_bin)
        else:
            set_timer('spk_update', v.audio_bin, False)


def reward (event):
    "reward state"
    if event == 'entry':
        hw.audio.all_off()
        hw.visual.all_off()
        if v.n_lick___ >= 3:
            hw.reward.release()
            v.reward_number += 1
            print('{}, reward_number'.format(v.reward_number))
        v.n_lick___ = 0
        timed_goto_state('trial', v.IT_duration)


# State independent behaviour.
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    Executes before the state code.
    """
    if event == "lick":
        v.n_lick___ += 1
    elif event == 'spk_update':
        v.spk_dir = randint(0,6)
        print('{}, spk_direction'.format(v.spk_dir))
        hw.audio.cue(v.spk_dir)
    elif event == 'session_timer':
        stop_framework()

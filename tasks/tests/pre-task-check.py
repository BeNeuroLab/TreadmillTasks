# Task to check for reward, leds, speakers

from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['intertrial', 'led_on', 'spk_sweep']

events = ['lick',
          'session_timer','cursor_update'
          'motion']

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 30 * minute
v.reward_duration = 5 * second
v.trial_number = 0

# intertrial params
v.min_IT_movement = 5  # cm - must be a multiple of 5
v.x___ = 0
v.y___ = 0

# trial params
v.trial_len = 1 * second


v.last_spk___ = 1
v.next_spk___ = 0

v.spks___ = [0, 1, 2, 3, 4, 5, 6]
v.leds___ = [1, 2, 3, 4, 5]



# -------------------------------------------------------------------------
# State-independent Code
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
# Define behaviour.
# -------------------------------------------------------------------------


# Run start and stop behaviour.
def run_start():
    "Code here is executed when the framework starts running."
    set_timer('session_timer', v.session_duration, True)
    hw.reward.sol.on()    

def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.light.all_off()
    hw.reward.sol.off()
    hw.motionSensor.off()
    hw.off()

# State behaviour functions.
def intertrial(event):
    "intertrial state behaviour"
    hw.light.all_off()
    timed_goto_state('led_on', v.reward_duration)

def led_on(event):
    hw.light.all_on()
    timed_goto_state('spk_sweep', v.reward_duration)

def spk_sweep(event):
    if event == 'entry':
        hw.light.all_off()
        hw.sound.cue(v.next_spk___)
        set_timer('cursor_update', v.trial_len, False)
    elif event == 'cursor_update':
        set_timer('cursor_update', v.trial_len, False)    



# State independent behaviour.
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    """
    if event == 'cursor_update':
        spk_dir = next_spk()
        hw.sound.cue(spk_dir)

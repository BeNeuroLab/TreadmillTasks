# PyTreadmillTask

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial',
          'gap']

events = ['lick',
          'session_timer',
          'motion']

initial_state = 'trial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 10 * minute
v.reward_duration = 30 * ms
v.reward_number = 0
v.stim_dir = None
v.n_lick___ = 0
v.max_IT_duration = 10 * second
v.max_led_duration = 3 * second

# -------------------------------------------------------------------------
# State-independent Code
# -------------------------------------------------------------------------


# Run start and stop behaviour.
def run_start():
    "Code here is executed when the framework starts running."
    set_timer('session_timer', v.session_duration, True)
    hw.audio.command(0x0D)

def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.LED_Delivery.all_off()
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
        timed_goto_state('gap', 2*second)
        hw.audio.cue(v.n_lick___)
        try:
            hw.LED_Delivery.cue_led(v.n_lick___)
        except: pass

def gap(event):
    "penalty state"
    if event == 'entry':
        timed_goto_state('trial', 2*second)
        if  v.n_lick___ >=6:
            v.n_lick___ =0
        else:  v.n_lick___ +=1
        hw.audio.all_off()


# State independent behaviour.
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    Executes before the state code.
    """
    if event == "lick":
        v.n_lick___ += 1
    elif event == 'session_timer':
        hw.motionSensor.stop()
        stop_framework()

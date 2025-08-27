# PyTreadmillTask

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math
import uarray

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['intertrial', 'reward']

events = ['intertrial_timer',
          'reward_timer',
           'lick',
          'lick_off',]

initial_state = 'reward'

# session params
v.i = 1

v.reward_duration = 2000 * ms
v.inter_trial_duration = 1000 * ms

def run_start():
    # Code here is executed when the framework starts running.
    hw.light.start()
   

def reward(event):
    if event == 'entry':
        set_timer('reward_timer', v.reward_duration, False)
        hw.light.cue(v.i)
    elif event == 'exit':
        disarm_timer('reward_timer')
    elif event == 'reward_timer':
        goto_state('intertrial')

def intertrial(event):
    if event == 'entry':
        set_timer('intertrial_timer', v.inter_trial_duration, False)
        hw.light.cue(50)
        v.i += 1
    elif event == 'exit':
        disarm_timer('intertrial_timer')
    elif event == 'intertrial_timer':
        goto_state('reward')

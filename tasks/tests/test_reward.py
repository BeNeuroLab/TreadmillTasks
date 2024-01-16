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
v.session_duration = 1 * hour

v.reward_duration = 5000 * ms
v.inter_trial_duration = 1000 * ms

def reward(event):
    if event == 'entry':
        set_timer('reward_timer', v.reward_duration, False)
        hw.rewardSol.on()
        print('{}, reward_on'.format(get_current_time()))
    elif event == 'exit':
        disarm_timer('reward_timer')
    elif event == 'reward_timer':
        hw.rewardSol.off()
        goto_state('intertrial')

def intertrial(event):
    if event == 'entry':
        set_timer('intertrial_timer', v.inter_trial_duration, False)
        print('{}, reward_off'.format(get_current_time()))
    elif event == 'exit':
        disarm_timer('intertrial_timer')
    elif event == 'intertrial_timer':
        goto_state('reward')

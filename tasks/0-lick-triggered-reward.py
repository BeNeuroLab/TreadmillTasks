"reward on lick, half of the time, when sound and light match"
from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
states = ['trial',
          'reward']

events = ['lick',
          'session_timer',
          'spk_update']

initial_state = 'trial'

# -------------------------------------------------------------------------
v.session_duration = 15 * minute
v.reward_duration = 60 * ms
v.reward_number = 0

v.trial_len = 0.75 * second #--> change to 1?
v.led_len = 50 * ms

# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.reward.reward_duration = v.reward_duration
    set_timer('session_timer', v.session_duration, True)
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

def run_end():
    "Code here is executed when the framework stops running."
    hw.reward.stop()
    hw.cameraTrigger.stop()
    hw.off()

# -------------------------------------------------------------------------
def trial(event):
    "led at first, and spk update at later bins"
    if event == 'lick':  # lick during the trial delays the sweep
        goto_state('reward')

def reward (event):
    "reward state"
    if event == 'entry':
        timed_goto_state('trial', v.trial_len)
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))

def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'session_timer':
        stop_framework()
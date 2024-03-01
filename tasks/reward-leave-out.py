# 1-led-reward-association: lining speakers with the mid LED and release the reward.

from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial',
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
v.leave_out_trials_delay = 20 * minute
v.start_leave_out_trials = False
v.reward_duration = 30 * ms
v.reward_number = 0
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
    hw.light.all_off()
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.threshold = 10

def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.light.all_off()
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
        hw.light.cue(3)
        set_timer('spk_update', v.audio_bin, False)
    elif event == 'spk_update':
        if hw.audio.active == hw.light.active:  # speaker lines up with LED
            if v.start_leave_out_trials is False:
                timed_goto_state('reward', v.audio_bin)
            else:
                timed_goto_state('cond_reward', v.audio_bin)
        else:
            set_timer('spk_update', v.audio_bin, False)


def reward (event):
    "reward state"
    if event == 'entry':
        hw.audio.all_off()
        hw.light.all_off()
        if v.n_lick___ >= 3:
            hw.reward.release()
            v.reward_number += 1
            print('{}, reward_number'.format(v.reward_number))
        v.n_lick___ = 0
        timed_goto_state('trial', v.IT_duration)

def cond_reward(event):
    

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
        if v.start_leave_out_trials if False:
            if v.session_duration - timer_remaining('session_timer') > v.leave_out_trials_delay:
                v.start_leave_out_trials = True
        spk_dir = randint(0,6)
        print('{}, spk_direction'.format(spk_dir))
        hw.audio.cue(spk_dir)
    elif event == 'session_timer':
        stop_framework()

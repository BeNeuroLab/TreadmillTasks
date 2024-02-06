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
v.n_lick___ = 5
v.n_avail_reward___ = 0
v.max_bin = 8  # no reward after 8 rand speakers are activated (~30% trials)
v.consecutive_bins___ = 0
v.IT_duration = 3 * second
v.audio_bin = 500 * ms



# -------------------------------------------------------------------------
# State-independent Code
# -------------------------------------------------------------------------

def next_spk():
    """
    returns the possible next speakers, [same, before, after]
    """
    assert len(hw.audio.active)==1, 'one one speaker can be active'
    spks = sorted(list(hw.audio.speakers.keys()))
    now = hw.audio.active[0]
    out = [now]  # current one
    if now == spk[-1]:  # last spk is active
        out.extend([spk[-2], spk[-2]])
    elif now == spk[0]:
        out.extend([spks[1], spks[1]])  # first spk is active
    else:
        out.extend([spks[now - 1], spks[now + 1]])
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
        hw.visual.cue(choice([2,4]))  # choose from led 2 or 4 as the cue
        hw.audio.cue(choice([0,6]))  # start the trial from one of the end speakers
        set_timer('spk_update', v.audio_bin, False)
        v.consecutive_bins___ = 0
    elif event == 'spk_update':
        if hw.audio.active == hw.visual.active:  # speaker lines up with LED
            timed_goto_state('reward', v.audio_bin)
        elif v.consecutive_bins___ >= v.max_bin:  # no reward after 8 rand speakers are activated
            timed_goto_state('penalty', v.audio_bin)
        else:
            set_timer('spk_update', v.audio_bin, False)


def reward (event):
    "reward state"
    if event == 'entry':
        hw.audio.all_off()
        hw.visual.all_off()
        if v.n_avail_reward___ <= 5:
            hw.reward.release()
            v.n_avail_reward___ += 1
            v.reward_number += 1
            print('{}, reward_number'.format(v.reward_number))
        v.n_lick___ = 0
        timed_goto_state('trial', v.IT_duration)

def penalty (event):
    "penalty state"
    if event == 'entry':
        hw.audio.all_off()
        hw.visual.all_off()
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
        if v.n_lick___ > 2:
            v.n_avail_reward___ = 0
    elif event == 'spk_update':
        spk_dir = choice(next_spk())
        print('{}, spk_direction'.format(spk_dir))
        hw.audio.cue(spk_dir)
        v.consecutive_bins___ += 1
    elif event == 'session_timer':
        stop_framework()

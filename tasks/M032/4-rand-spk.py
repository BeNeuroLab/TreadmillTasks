# 1-led-reward-association: lining speakers with the mid LED and release the reward.

from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial',
          'reward',
          'free_reward',
          'penalty',
          'intertrial']

events = ['lick',
          'motion',
          'session_timer',
          'spk_update',
          'trial_timeout']

initial_state = 'trial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 45 * minute
v.reward_duration = 25 * ms
v.min_IT_movement___ = 10  # cm - must be a multiple of 5

v.reward_number = 0
v.last_spk___ = 0
v.next_spk___ = 5
v.next_led___ = 1
v.IT_duration = 7 * second
v.penalty_duration = 10 * second
v.sound_bins = (1 * second, 2 * second, 3 * second)

v.spks___ = [1, 2, 3, 4, 5]
v.leds___ = [1, 3, 5]



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
        out = active_spk_idx + 1 if active_spk < v.spks___[-1] else active_spk_idx - 1
    else:
        out = active_spk_idx - 1 if active_spk > v.spks___[0] else active_spk_idx + 1

    v.last_spk___ = active_spk

    return v.spks___[out]


# -------------------------------------------------------------------------
# Define behaviour.
# -------------------------------------------------------------------------

# Run start and stop behaviour.
def run_start():
    "Code here is executed when the framework starts running."
    hw.sound.set_volume(15)  # Between 1 - 30
    utime.sleep_ms(20)  # wait for the sound player to be ready
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.min_IT_movement___
    hw.sound.start()
    hw.light.all_off()
    hw.reward.reward_duration = v.reward_duration
    set_timer('session_timer', v.session_duration, True)
    set_timer('trial_timeout', 20 * second, False)  # timeout in case of no engagement
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()


def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.light.all_off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.cameraTrigger.stop()
    hw.sound.all_off()
    hw.sound.stop()
    hw.off()

# State behaviour functions.

def trial(event):
    "led at first, and spk update at later bins"
    if event == 'entry':
        hw.light.cue(v.next_led___)
        hw.sound.cue(v.next_spk___)
        print('{}, spk_direction'.format(v.next_spk___))
        print('{}, led_direction'.format(v.next_led___))
        set_timer('spk_update', choice(v.sound_bins), False)
    elif event == 'lick':  # lick during the trial delays the sweep
        goto_state('penalty')
    elif event == 'spk_update':
        if hw.sound.active == hw.light.active:  # speaker lines up with LED
            if random() > 0.9:  # 10% chance of free reward
                goto_state('free_reward')
            else:
                goto_state('reward')
        else:
            set_timer('spk_update', choice(v.sound_bins), False)
    elif event == 'trial_timeout':
        goto_state('intertrial')
    elif event == 'exit':
        disarm_timer('spk_update')

def free_reward(event):
    "free reward state"
    if event == 'entry':
        timed_goto_state('penalty', 1 * minute)
        disarm_timer('trial_timeout')
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
    elif event == 'lick':
        goto_state('intertrial')

def reward (event):
    "reward state"
    if event == 'entry':
        timed_goto_state('trial', v.sound_bins[-1])
        v.next_spk___ = next_spk()  # in case of no lick, sweep continues
        v.next_led___ = hw.light.active[0]
    elif event == 'lick':
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        goto_state('intertrial')
    elif event == 'trial_timeout':
        reset_timer('trial_timeout', v.sound_bins[-1] + 1, False)  # to delay the timeout so the state changes

def intertrial (event):
    "intertrial state"
    if event == 'entry':
        hw.sound.all_off()
        hw.light.all_off()
        timed_goto_state('trial', v.IT_duration)
        v.next_spk___ = choice([v.spks___[0],v.spks___[-1]])
        v.next_led___ = choice([el for el in v.leds___ if el != v.next_spk___])
    elif event == 'exit':
        reset_timer('trial_timeout', 20 * second, False)

def penalty(event):
    "penalty state"
    if event == 'entry':
        hw.sound.all_off()
        hw.light.all_off()
        timed_goto_state('trial', v.penalty_duration)
        hw.light.blink(v.next_led___, freq=10, n_pulses=50)
        v.next_spk___ = choice([v.spks___[0],v.spks___[-1]])
        v.next_led___ = choice([el for el in v.leds___ if el != v.next_spk___])
        hw.sound.cue_array([0,6])
    elif event == 'exit':
        reset_timer('trial_timeout', 20 * second, False)

def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    Executes before the state code.
    """
    if event == 'spk_update':
        spk_dir = next_spk()
        print('{}, spk_direction'.format(spk_dir))
        hw.sound.cue(spk_dir)
    elif event == 'session_timer':
        stop_framework()

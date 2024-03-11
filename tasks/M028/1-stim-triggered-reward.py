# 1-stim-triggered-reward.py lick at the stimulus to get extra reward, then stop licking for the next stimulus

from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial',
          'intertrial']

events = ['lick',
          'motion',
          'session_timer',
          'trial_timeout']

initial_state = 'trial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 20 * minute
v.reward_duration = 30 * ms
v.min_IT_movement___ = 10  # cm - must be a multiple of 5
v.reward_gap___ = 500 * ms

v.reward_number = 0
v.IT_duration = 7 * second

v.spks___ = [1, 3, 5]  # 3 spread-out speaker


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
        stim_chance = random()
        next_dir = choice(v.spks___)
        if stim_chance > 0.5:
            hw.light.cue(next_dir)
            hw.sound.cue(next_dir)
            print('{}, spk_direction'.format(next_dir))
            print('{}, led_direction'.format(next_dir))
        elif stim_chance <= 0.25:
            hw.light.cue(next_dir)
            hw.sound.all_off()
            print('{}, led_direction'.format(next_dir))
        else:
            hw.light.all_off()
            hw.sound.cue(next_dir)
            print('{}, spk_direction'.format(next_dir))

    elif event == 'lick':  # lick during the trial delays the sweep
        timed_goto_state('intertrial', v.reward_gap___)

def intertrial (event):
    "intertrial state"
    if event == 'entry':
        set_timer('trial_timeout', v.IT_duration, False)  # timeout in case of no engagement
        hw.sound.all_off()
        hw.light.all_off()
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))

    elif event == 'lick':
        reset_timer('trial_timeout', v.IT_duration, False)

    elif event == 'trial_timeout':
        goto_state('trial')

def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    Executes before the state code.
    """
    if event == 'session_timer':
        stop_framework()

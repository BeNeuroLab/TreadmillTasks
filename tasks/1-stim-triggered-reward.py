"1-stim-triggered-reward.py"

import utime
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
v.session_duration = 45 * minute
v.reward_duration = 30 * ms
v.min_IT_movement___ = 10  # cm - must be a multiple of 5

v.reward_gap___ = 500 * ms

v.reward_number = 0
v.IT_duration = 7 * second

v.spks___ = [0, 1, 2, 3, 4, 5, 6]
v.leds___ = [1, 2, 3, 4, 5]


# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.sound.set_volume(8)  # Between 1 - 30
    utime.sleep_ms(20)  # wait for the sound player to be ready
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    hw.sound.start()
    hw.light.all_off()
    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

def run_end():
    "Code here is executed when the framework stops running."
    hw.light.all_off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.sound.stop()
    hw.off()


# -------------------------------------------------------------------------
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
            goto_state('reward')
        else:
            set_timer('spk_update', choice(v.sound_bins), False)
    elif event == 'trial_timeout':
        goto_state('intertrial')
    elif event == 'exit':
        disarm_timer('spk_update')

def reward (event):
    "reward state"
    if event == 'entry':
        timed_goto_state('trial', v.sound_bins[-1])
        v.next_spk___ = next_spk()  # in case of no lick, sweep continues
        #v.next_led___ = hw.light.active[0]
    elif event == 'lick':
        hw.reward.release()
        v.reward_number += 1
        v.relative_reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        if v.relative_reward_number == v.max_reward: # Change LED
            v.relative_reward_number = 0
            index = v.leds___.index(v.next_led___)
            if index < len(v.leds___):
                v.next_led___ = v.leds___[index + 1]
            else:
                v.next_led___ = v.leds___[0]  # If reached the end
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
        #v.next_led___ = 2  # choice([el for el in v.leds___ if el != v.next_spk___])
    elif event == 'exit':
        reset_timer('trial_timeout', v.time_to_timeout, False)

def penalty(event): # First part of the penalty: Mantain spk, blinking LED
    "penalty state"
    if event == 'entry':
        timed_goto_state('penalty_reset', v.penalty_duration/2)
        hw.light.blink(v.next_led___, freq=10, n_pulses=50)
         
def penalty_reset(event): # Second part of the penalty: spk off, LED on
    "penalty state"
    if event == 'entry':
        timed_goto_state('trial', v.penalty_duration/2)
        hw.sound.all_off()    
        hw.light.cue(v.next_led___)
        v.next_spk___ = choice([v.spks___[0],v.spks___[-1]])    
        #v.next_led___ = 2  # choice([el for el in v.leds___ if el != v.next_spk___])
        #hw.sound.cue_array([0,6])
    elif event == 'exit':
        reset_timer('trial_timeout', v.time_to_timeout, False)    

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

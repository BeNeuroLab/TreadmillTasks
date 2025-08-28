"""main BCI task, similar to task 5
target always on during the speaker sweep
there are also catch trials where led and spk never turn on and reward is released AFTER a lick
"""
import utime
from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial',
        'cursor_match',
        'reward',
        'catch_reward',
        'catch_cursor_match'
        ]

events = ['lick',
        'motion',
        'cursor_update',
        'session_timer']

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 90 * minute
v.reward_duration = 30 * ms
v.hold_duration = 200 * ms

v.catch_chance = 0.05  # 10% chance of catch trial in cursor match
v.max_ommitted_rewards = 15  # maximum number of rewards ommitted due to catch trials
v.n_ommitted_reward = 0  # number of ommitted rewards due to catch trials

v.reward_number = 0
v.IT_duration = 5 * second


# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    hw.bci_link.start(do_led_strip = True)
    utime.sleep_ms(20)  # wait for the light
    hw.bci_link.light.all_red()
    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

def run_end():
    "Code here is executed when the framework stops running."
    hw.bci_link.light.all_off()
    hw.bci_link.light.stop()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.off()


# -------------------------------------------------------------------------
def trial(event):
    "Trial state"
    if event == 'cursor_update':
        spk_dir = hw.bci_link.spk
        hw.bci_link.light.cue(spk_dir)
        if spk_dir == 100:
            if random() < v.catch_chance and v.n_ommitted_reward < v.max_ommitted_rewards:
                goto_state('catch_cursor_match')
            else:
                goto_state('cursor_match')

def cursor_match(event):
    "when led and spk line up"
    if event == 'entry':
        timed_goto_state('reward', v.hold_duration)
    elif event == 'cursor_update':
        spk_dir = hw.bci_link.spk
        hw.bci_link.light.cue(spk_dir)
        if spk_dir != 100:
            goto_state('trial')

def reward (event):
    "reward state"
    if event == 'entry':
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        hw.bci_link.light.all_red()
        timed_goto_state('trial', v.IT_duration)

def catch_cursor_match(event):
    "cursor match without led and spk"
    if event == 'entry':
        timed_goto_state('catch_reward', v.hold_duration)
    elif event == 'cursor_update':
        spk_dir = hw.bci_link.spk
        hw.bci_link.light.cue(spk_dir)
        if spk_dir != 100:
            goto_state('trial')

def catch_reward(event):
    "reward state for catch trials"
    if event == 'entry':
        timed_goto_state('trial', v.IT_duration)
    elif event == 'lick':  # reward should be released
        v.n_ommitted_reward += 1
        print('{}, ommitted_reward'.format(v.n_ommitted_reward))
        goto_state('reward')
    if event == 'exit':
        hw.bci_link.light.all_red()



def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'session_timer':
        stop_framework()

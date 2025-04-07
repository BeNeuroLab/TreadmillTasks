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
v.session_duration = 30 * minute
v.reward_duration = 50 * ms
v.reward_number = 0

v.spk_freqs = [2181, 12336]
v.leds = [2, 4]

v.trial_len = 1 * second 

# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.speaker.set_volume(10)
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    set_timer('session_timer', v.session_duration, True)
    print('{}, before_camera_trigger'.format(get_current_time()))
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    hw.cameraTrigger.start()

def run_end():
    "Code here is executed when the framework stops running."
    hw.light.all_off()
    hw.speaker.off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.off()

# -------------------------------------------------------------------------
def trial(event):
    "led at first, and spk update at later bins"
    if event == 'entry':
        hw.light.all_off()
        hw.speaker.off()
    elif event == 'lick':  # lick during the trial delays the sweep
        v.sound_target = choice(v.spk_freqs)
        if v.sound_target < 5000:
            v.led_target = v.leds[0]
        else:
            v.led_target = v.leds[1]
        hw.light.cue(v.led_target)
        hw.speaker.sine(v.sound_target)
        print('{} Hz'.format(v.sound_target))
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
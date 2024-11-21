"""main BCI task, similar to task 5
target always on during the speaker sweep

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
          'timeout']

events = ['lick',
          'motion',
          'cursor_update',
          'trial_timer',
          'session_timer']

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 60 * minute
v.reward_duration = 40 * ms
v.hold_duration = 100 * ms
v.timeout_duration = 20 * second
v.timeout_timer = 1 * minute

v.reward_number = 0
v.IT_duration = 5 * second

v.spks___ = [0, 1, 2, 3, 4, 5, 6]
v.leds___ = [1, 2, 3, 4, 5]
v.next_led___ = v.leds___[2]


# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.sound.set_volume(8)  # Between 1 - 30
    utime.sleep_ms(20)  # wait for the sound player to be ready
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    hw.sound.start()
    hw.light.all_off()
    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

    set_timer('trial_timer', v.timeout_timer, True)

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
    "Trial state"
    if event == 'entry':
        hw.light.all_off()
    elif event == 'cursor_update':
        if v.next_led___ in hw.sound.active:
            goto_state('cursor_match')
    elif event == 'trial_timer':
        goto_state('timeout')

def cursor_match(event):
    "when led and spk line up"
    if event == 'entry':
        hw.light.cue(v.next_led___)
        print('{}, led_direction'.format(v.next_led___))
        pause_timer('trial_timer')
        timed_goto_state('reward', v.hold_duration)
    elif event == 'cursor_update':
        goto_state('trial')
    elif event == 'exit':
        unpause_timer('trial_timer')

def reward (event):
    "reward state"
    if event == 'entry':
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        hw.light.all_off()
        timed_goto_state('trial', v.IT_duration)
        v.next_led___ = choice(v.leds___)
    elif event == 'exit':
        reset_timer('trial_timer', v.timeout_timer, True)

def timeout(event):
    "timeout state"
    if event == 'entry':
        hw.light.all_off()
        hw.sound.all_off()
        v.next_led___ = choice(v.leds___)
        timed_goto_state('trial', v.timeout_duration)
    elif event == 'cursor_update':
        hw.sound.all_off()
    elif event == 'exit':
        reset_timer('trial_timer', v.timeout_timer, True)


def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'cursor_update':
        spk_dir = hw.bci_link.spk
        print('{}, spk_direction'.format(spk_dir))
        try:  # Try is more efficient than If statement
            hw.sound.cue(spk_dir)
        except:  # if the spk_dir is not valid
            pass
    elif event == 'session_timer':
        stop_framework()

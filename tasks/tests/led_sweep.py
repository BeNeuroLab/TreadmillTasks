"""led sweep every 1s
"""

import utime
from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial']

events = ['lick',
          'motion',
          'cursor_update',
          'session_timer']

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 15 * minute
v.sound_bins = (1 * second,)

v.last_led___ = 2
v.next_led___ = 1

v.leds___ = [1, 2, 3, 4, 5]
v.next_led___ = v.leds___[-1]


# -------------------------------------------------------------------------
def next_led():
    """
    returns the next speakers, in either direction of the sweep
    """
    assert len(hw.light.active) == 1, 'one speaker can be active'
    active_led = hw.light.active[0]
    active_led_idx = v.leds___.index(active_led)

    if active_led > v.last_led___:
        if active_led < v.leds___[-1]:
            out = active_led_idx + 1
        else:
            out = active_led_idx - 1
    else:
        if active_led > v.leds___[0]:
            out = active_led_idx - 1
        else:
            out = active_led_idx + 1

    v.last_led___ = active_led

    return v.leds___[out]


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
    "trial state"
    if event == 'entry':
        hw.sound.all_off()
        hw.light.cue(v.next_led___)
        print('{}, led_direction'.format(v.next_led___))
        set_timer('cursor_update', choice(v.sound_bins), False)
    elif event == 'cursor_update':
        set_timer('cursor_update', choice(v.sound_bins), False)


def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'cursor_update':
        led_dir = next_led()
        print('{}, led_direction'.format(led_dir))
        hw.light.cue(led_dir)
    elif event == 'session_timer':
        stop_framework()

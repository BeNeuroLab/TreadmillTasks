"""speaker sweep every 1s
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
v.session_duration = 10 * minute
v.sound_bins = (1 * second,)

v.last_spk___ = 1
v.next_spk___ = 0

v.spks___ = [0, 1, 2, 3, 4, 5, 6]
v.leds___ = [1, 2, 3, 4, 5]
v.next_led___ = v.leds___[-1]


# -------------------------------------------------------------------------
def next_spk():
    """
    returns the next speakers, in either direction of the sweep
    """
    assert len(hw.sound.active)==1, 'one speaker can be active'
    active_spk = hw.sound.active[0]
    active_spk_idx = v.spks___.index(active_spk)

    if active_spk > v.last_spk___:
        if active_spk < v.spks___[-1]:
            out = active_spk_idx + 1
        else:
            out = active_spk_idx - 1
    else:
        if active_spk > v.spks___[0]:
            out = active_spk_idx - 1
        else:
            out = active_spk_idx + 1

    v.last_spk___ = active_spk

    return v.spks___[out]


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
        hw.light.all_off()
        hw.sound.cue(v.next_spk___)
        print('{}, spk_direction'.format(v.next_spk___))
        set_timer('cursor_update', choice(v.sound_bins), False)
    elif event == 'cursor_update':
        set_timer('cursor_update', choice(v.sound_bins), False)


def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'cursor_update':
        spk_dir = next_spk()
        print('{}, spk_direction'.format(spk_dir))
        hw.sound.cue(spk_dir)
    elif event == 'session_timer':
        stop_framework()

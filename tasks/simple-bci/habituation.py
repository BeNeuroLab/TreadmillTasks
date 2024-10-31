# habituation task for the simple bci task

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import utime


# -------------------------------------------------------------------------
states = ['trial',
          'intertrial']

events = ['motion',
          'session_timer',
          'spk_update']

initial_state = 'trial'


# -------------------------------------------------------------------------
v.session_duration = 15 * minute
v.IT_duration = 2 * second
v.trial_len = 5 * second

v.last_spk___ = 1
v.next_spk___ = 0

v.spks___ = [3]


# -------------------------------------------------------------------------
def next_spk():
    """
    returns the next speakers, in either direction of the sweep
    """
    assert len(hw.sound.active)==1, 'one speaker can be active'
    active_spk = hw.sound.active[0]
    active_spk_idx = v.spks___.index(active_spk)
    if len(v.spks___) == 1:
        return v.spks___[0]

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
    hw.sound.set_volume(5)  # Between 1 - 30
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
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.light.all_off()
    hw.motionSensor.off()
    hw.cameraTrigger.stop()
    hw.sound.all_off()
    hw.sound.stop()
    hw.off()

def trial(event):
    "light and auditory stimulus"
    if event == 'entry':
        hw.sound.cue(v.next_spk___)
        print('{}, spk_direction'.format(v.next_spk___))
        timed_goto_state('intertrial', v.trial_len)

def intertrial (event):
    "gap between stimulus"
    if event == 'entry':
        v.next_spk___ = next_spk()  # sweep continues
        hw.sound.all_off()
        timed_goto_state('trial', v.IT_duration)


def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'session_timer':
        stop_framework()

# habituation task that sweeps the leds and spks at the same time in a sequential order

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import utime

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['trial',
          'intertrial']

events = ['motion',
          'session_timer',
          'spk_update']

initial_state = 'trial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters

# session params
v.session_duration = 15 * minute
v.IT_duration = 2 * second
v.trial_len = 5 * second

v.last_spk___ = 1
v.next_spk___ = 0

v.spks___ = [0, 1, 2, 3, 4, 5, 6]
v.leds___ = [1, 2, 3, 4, 5]


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
        if active_spk < v.spks___[-1]:
            out = active_spk_idx + 1
        else:
            out = active_spk_idx - 1
            switch_leds()
    else:
        if active_spk > v.spks___[0]:
            out = active_spk_idx - 1
        else:
            out = active_spk_idx + 1
            switch_leds()

    v.last_spk___ = active_spk

    return v.spks___[out]

def switch_leds():
    """
    switch which half of LEDs to turn on on each call
    """
    if v.leds___[0] in hw.light.active:
        out = v.leds___[:3]
    elif v.leds___[-1] in hw.light.active:
        out = v.leds___[-3:]
    else:
        out = v.leds___[:3]

    print('{}, led_direction'.format(out))
    hw.light.cue_array(out)


# -------------------------------------------------------------------------
# Define behaviour.
# -------------------------------------------------------------------------

# Run start and stop behaviour.
def run_start():
    "Code here is executed when the framework starts running."
    hw.sound.set_volume(15)  # Between 1 - 30
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
        # Continue sweep
        v.next_spk___ = next_spk()  # sweep continues
        timed_goto_state('trial', v.IT_duration)




# State independent behaviour.
        
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    Executes before the state code.
    """
    if event == 'session_timer':
        stop_framework()

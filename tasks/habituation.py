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
v.IT_duration = 0.5 * second
v.trial_len = 10 * second

v.last_spk___ = 1
v.next_spk___ = 5
v.next_led___ = 5

v.spks___ = sorted(list(hw.audio.speakers.keys()))
v.leds___ = sorted(list(hw.visual.LEDs.keys()))
# Remove side speakers
v.spks___ = v.spks___[1:-1]


# -------------------------------------------------------------------------
# State-independent Code
# -------------------------------------------------------------------------

def next_spk():
    """
    returns the next speakers, in either direction of the sweep
    """
    assert len(hw.audio.active)==1, 'one one speaker can be active'
    active_spk = hw.audio.active[0]

    if active_spk > v.last_spk___:
        out = active_spk + 1 if active_spk < v.spks___[-1] else active_spk - 1
    else:
        out = active_spk - 1 if active_spk > v.spks___[0] else active_spk + 1
    
    v.last_spk___ = active_spk

    return out


# -------------------------------------------------------------------------
# Define behaviour.
# -------------------------------------------------------------------------

# Run start and stop behaviour.
def run_start():
    "Code here is executed when the framework starts running."
    hw.audio.set_volume(20)  # Between 1 - 30
    utime.sleep_ms(20)  # wait for the audio player to be ready
    hw.audio.start()
    hw.cameraTrigger.start()
    hw.motionSensor.record()
    hw.visual.all_off()
    hw.motionSensor.threshold = 10
    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))

def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.visual.all_off()
    hw.motionSensor.off()
    hw.cameraTrigger.stop()
    hw.audio.all_off()
    hw.audio.stop()
    hw.off()

# State behaviour functions.

def trial(event):
    "visual and auditory stimulus"
    if event == 'entry':
        hw.visual.cue(v.next_led___)
        hw.audio.cue(v.next_spk___)
        print('{}, spk_direction'.format(v.next_spk___))
        print('{}, led_direction'.format(v.next_led___))
        timed_goto_state('intertrial', v.trial_len)
    
def intertrial (event):
    "gap between stimulus"
    if event == 'entry':
        # Continue sweep
        v.next_spk___ = next_spk()  # sweep continues
        v.next_led___ = v.next_spk___ # turn on the same LED
        hw.audio.all_off()
        hw.visual.all_off()
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

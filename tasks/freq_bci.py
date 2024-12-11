"""
BCI frequency-based reward task:
- On frequency update in trial:
  * If freq <= low_threshold: LED_low on, sound on, move to reward state.
  * If freq >= high_threshold: LED_high on, sound on, move to reward state.
  * Else (intermediate): no LED, sound at freq, stay in trial.
- In reward state:
  * On entry, start hold_timer = hold_duration.
  * Before hold_duration passes: licks do nothing.
  * After hold_duration passes: a lick delivers reward and then go to intertrial.
  * If trial_timer ends with no reward, go to intertrial.
- In intertrial state:
  * Wait IT_duration, then return to trial.
- Session ends after session_duration.
- Print statements follow the "val, message" format.
"""

import utime
from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'trial',
    'reward',
    'intertrial',
]

events = [
    'session_timer',
    'cursor_update',
    'trial_timer',
    'IT_timer',
    'lick',
    'motion',
    'hold_timer',
    'reward_timer'
]

initial_state = 'trial'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
v.session_duration = 30 * minute

# Thresholds (zero-indexed)
v.low_threshold = 2300
v.high_threshold = 13000

v.led_low = 2
v.led_high = 4

v.reward_duration = 40 * ms
v.hold_duration = 500 * ms     # Mouse must sustain freq for this duration
v.trial_duration = 10 * second # total trial duration (example)
v.IT_duration = 3 * second     # intertrial interval
v.reward_timer = 3 * second

v.reward_count = 0
v.hold_passed = False  # To track if hold_duration passed in reward state

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(8)
    utime.sleep_ms(20)
    hw.reward.reward_duration = v.reward_duration
    
    hw.light.all_off()
    hw.speaker.off()
    set_timer('session_timer', v.session_duration, True)
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

def run_end():
    hw.light.all_off()
    hw.reward.stop()
    hw.cameraTrigger.stop()
    hw.off()

# -------------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------------
def determine_zone(freq):
    if freq <= v.low_threshold:
        return 'low'
    elif freq >= v.high_threshold:
        return 'high'
    else:
        return 'intermediate'

# -------------------------------------------------------------------------
# States
# -------------------------------------------------------------------------
def trial(event):
    """
    In trial state:
    - On entry, set trial_timer.
    - On cursor_update, determine zone:
       * low/high -> LED on, sound on, goto reward
       * intermediate -> LED off, sound freq
    """
    if event == 'entry':
        hw.light.all_off()
        hw.speaker.off()
        set_timer('trial_timer', v.trial_duration)

    elif event == 'cursor_update':
        freq = hw.bci_link.spk
        if freq is None:
            freq = int((v.low_threshold + v.high_threshold)/2)
        print("{}, spk_direction".format(freq))
        hw.speaker.sine(freq)

        zone = determine_zone(freq)
        if zone == 'low':
            hw.light.cue(v.led_low)
            print("{}, led_direction".format(v.led_low))
            goto_state('reward')
        elif zone == 'high':
            hw.light.cue(v.led_high)
            print("{}, led_direction".format(v.led_high))
            goto_state('reward')
        else:
            hw.light.all_off()

    elif event == 'trial_timer':
        # Trial ended with no reward trigger
        goto_state('intertrial')

    elif event == 'session_timer':
        stop_framework()

def reward(event):
    """
    In reward state:
    - On entry, start hold_timer for hold_duration.
    - Before hold_timer event, licks do nothing.
    - On hold_timer event, v.hold_passed = True, now a lick gives reward.
    - On lick after hold_passed = True, give reward and goto intertrial.
    - If trial_timer ends with no lick after hold_passed, goto intertrial with no reward.
    """
    if event == 'entry':
        v.hold_passed = False
        set_timer('hold_timer', v.hold_duration, output_event=False)
        # output_event=False because we only use this internally.

    elif event == 'hold_timer':
        v.hold_passed = True
        set_timer('reward_timer', v.reward_timer) 

    elif event == 'lick':
        # If hold_passed is True, deliver reward
        if v.hold_passed:
            hw.reward.release()
            v.reward_count += 1
            print("{}, reward_number".format(v.reward_count))
            hw.light.all_off()
            hw.speaker.off()
            v.hold_passed = False
            goto_state('intertrial')
        # If lick before hold_passed, do nothing

    elif event == 'reward_timer':
        v.hold_passed = False
        # Trial ended with no reward given
        hw.light.all_off()
        hw.speaker.off()
        goto_state('intertrial')

    elif event == 'session_timer':
        stop_framework()

def intertrial(event):
    """
    intertrial state:
    - On entry, wait IT_duration, then go to trial
    """
    if event == 'entry':
        hw.light.all_off()
        hw.speaker.off()
        set_timer('IT_timer', v.IT_duration)

    elif event == 'IT_timer':
        goto_state('trial')

    elif event == 'session_timer':
        stop_framework()

def all_states(event):
    if event == 'session_timer':
        stop_framework()
    # motion event not used, just acknowledge
    if event == 'motion':
        pass

"""
BCI frequency-based reward task:
- Frequency from BCI sets LED and sound states.
- If freq < low_threshold: LED0 on, sound at freq, track hold for reward.
- If freq > high_threshold: LED1 on, sound at freq, track hold for reward.
- If intermediate: no LED, sound at freq, no reward tracking.
- If reward criteria met (hold_duration in low or high zone), deliver reward.
- If no reward by trial end, go to intertrial (silence) period and then start new trial.
- Print statements follow required format.
- Events and states follow the naming conventions.
- Zero-indexed naming: e.g., led0, speaker0.
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
    'trial_timer',  # total trial duration
    'IT_timer',     # intertrial duration
    'lick',
    'motion'
]

initial_state = 'trial'

# -------------------------------------------------------------------------
# Variables (zero-indexed)
# -------------------------------------------------------------------------
v.session_duration = 30 * minute

# Thresholds (all zero-indexed conceptually)
v.low_threshold = 2300
v.high_threshold = 10000

# Hardware Assignments (zero-indexed)
# Assume speaker0 and speaker1 refer to different speaker outputs if available
# If only one speaker device, just interpret freq changes. 
# LED indexing zero-based
v.led_low = 0
v.led_high = 1

# Durations
v.reward_duration = 40 * ms
v.hold_duration = 1 * second
v.trial_duration = 20 * second
v.IT_duration = 10 * second  # intertrial duration
v.inter_trial_interval = 2 * second  # after reward

# Internal
v.freq_hold_start = None
v.current_zone = None   # 'low', 'intermediate', 'high'
v.reward_count = 0
v.reward_given = False

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.reward.reward_duration = v.reward_duration
    hw.speaker.set_volume(10)
    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration)
    print("val, session_start")

def run_end():
    hw.speaker.off()
    hw.light.all_off()
    hw.reward.stop()
    hw.cameraTrigger.stop()
    print("val, session_end")

# -------------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------------

def determine_zone(freq):
    if freq < v.low_threshold:
        return 'low'
    elif freq > v.high_threshold:
        return 'high'
    else:
        return 'intermediate'

def update_output(freq):
    # Turn off LEDs first
    hw.light.all_off()
    # Always play sound at current freq
    hw.speaker.sine(freq)

    zone = determine_zone(freq)
    if zone == 'low':
        hw.light.cue(v.led_low)    # led0 on
        print(f"val, led_direction:{v.led_low}")
    elif zone == 'high':
        hw.light.cue(v.led_high)   # led1 on
        print(f"val, led_direction:{v.led_high}")
    # intermediate: no LED

    # For print messages about speaker direction, since we are using freq directly:
    # If you want to specify which speaker index is active, you can do so here.
    # Assuming a single speaker device (speaker0) for all frequencies:
    print("val, spk_direction:0") 

    return zone

def reset_hold_timer():
    v.freq_hold_start = None

def handle_hold_timer(zone):
    # Only track reward in low or high zone
    if zone in ('low', 'high'):
        if v.freq_hold_start is None:
            v.freq_hold_start = get_current_time()
        else:
            elapsed = get_current_time() - v.freq_hold_start
            if elapsed >= v.hold_duration and not v.reward_given:
                goto_state('reward')
    else:
        reset_hold_timer()

# -------------------------------------------------------------------------
# States
# -------------------------------------------------------------------------

def trial(event):
    """
    Trial state where the main behavior happens.
    - On cursor_update, set sound and LED based on freq.
    - Track hold for reward if in low/high zone.
    - If trial_timer ends with no reward, go to intertrial.
    """
    if event == 'entry':
        v.reward_given = False
        reset_hold_timer()
        set_timer('trial_timer', v.trial_duration)
        print("val, trial_start")

    elif event == 'cursor_update':
        freq = hw.bci_link.freq
        if freq is None:
            freq = 0.0
        print(f"val, frequency:{freq}")

        v.current_zone = update_output(freq)
        handle_hold_timer(v.current_zone)

    elif event == 'trial_timer':
        # No reward given, go to intertrial
        if not v.reward_given:
            goto_state('intertrial')

    elif event == 'session_timer':
        stop_framework()


def reward(event):
    """
    Reward state starts with delivering reward.
    """
    if event == 'entry':
        hw.reward.release()
        v.reward_given = True
        v.reward_count += 1
        print(f"val, reward_number:{v.reward_count}")
        # Turn off LED and sound
        hw.speaker.off()
        hw.light.all_off()
        # After reward, short ITI before next trial.
        set_timer('IT_timer', v.inter_trial_interval)
        print("val, sol_direction:0") # Assuming solenoid0 for reward

    elif event == 'IT_timer':
        goto_state('trial')

    elif event == 'session_timer':
        stop_framework()


def intertrial(event):
    """
    Intertrial period after a failed trial.
    """
    if event == 'entry':
        hw.speaker.off()
        hw.light.all_off()
        set_timer('IT_timer', v.IT_duration)
        print("val, intertrial_start")

    elif event == 'IT_timer':
        goto_state('trial')

    elif event == 'session_timer':
        stop_framework()


def all_states(event):
    if event == 'session_timer':
        stop_framework()

    # If you have lick or motion events, you can handle them here or in states.
    # For now, just acknowledge they exist:
    if event == 'lick':
        print("val, lick_event")
    elif event == 'motion':
        print("val, motion_event")

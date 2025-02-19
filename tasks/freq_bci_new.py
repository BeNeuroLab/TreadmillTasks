import utime
from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'trial',
    'threshold_crossed',
    'reward',
    'intertrial'
]

events = [
    'session_timer',
    'cursor_update',
    'lick'
]

initial_state = 'trial'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
v.session_duration       = 45 * minute
v.reward_duration        = 40 * ms
v.hold_duration          = 200 * ms       # Hold period before lick can trigger reward
v.trial_duration         = 10 * second    # Maximum trial duration if no threshold is crossed
v.IT_duration            = 3 * second     # Intertrial interval (for fixed IT mode)
v.reward_timer_duration  = 2 * second     # Maximum duration in the reward state waiting for a lick
v.IT_mode                = "fixed"        # "fixed" or "baseline"

v.freq_bins              = [2181,2594,3084,3668,4362,5187,6169,7336,8724,10375,12338]
v.baseline_freq_range    = [3668, 7336]   # Frequencies considered baseline in IT mode

v.reward_count           = 0

# -------------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------------
def determine_zone(freq):
    """
    Returns 'low' if freq is below or equal to low_threshold,
    'high' if freq is above or equal to high_threshold,
    and 'intermediate' otherwise.
    """
    if freq <= v.freq_bins[0]:
        return 'low'
    elif freq >= v.freq_bins[-1]:
        return 'high'
    else:
        return 'intermediate'

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(8)
    utime.sleep_ms(20)
    hw.reward.reward_duration = v.reward_duration
    hw.speaker.off()
    # Ensure session termination is scheduled.
    set_timer('session_timer', v.session_duration, True)
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

def run_end():
    hw.reward.stop()
    hw.speaker.off()
    hw.cameraTrigger.stop()
    hw.off()

# -------------------------------------------------------------------------
# States
# -------------------------------------------------------------------------
def trial(event):
    """
    In the trial state:
      - On entry, the speaker is turned off and a timed transition to intertrial is scheduled.
      - On cursor_update, the task reads the frequency. If it is in the low or high zone,
        it transitions immediately to the threshold_crossed state (canceling the pending trial timeout).
      - Intermediate frequencies continue to provide auditory feedback.
    """
    if event == 'entry':
        hw.speaker.off()
        # Automatically move to intertrial after trial_duration if no threshold crossing occurs.
        timed_goto_state('intertrial', v.trial_duration)
    elif event == 'cursor_update':
        freq = hw.bci_link.spk
        if freq is None:
            freq = v.freq_bins[5]  # Default to a mid-range frequency
        print("{}, spk_frequency".format(freq))
        hw.speaker.sine(freq)
        zone = determine_zone(freq)
        if zone in ['low', 'high']:
            goto_state('threshold_crossed')  # Cancel trial timeout and move to threshold_crossed state
        else:
            print("{}, frequency update".format(freq))
    elif event == 'session_timer':
        stop_framework()

def threshold_crossed(event):
    """
    In the threshold_crossed state:
      - On entry, a hold period is initiated using timed_goto_state.
      - Licks during this hold period are ignored.
      - After v.hold_duration, the task automatically transitions to the reward state.
    """
    if event == 'entry':
        print("threshold crossed")
        timed_goto_state('reward', v.hold_duration)
    elif event == 'lick':
        print("lick detected during hold period")
    elif event == 'session_timer':
        stop_framework()

def reward(event):
    """
    In the reward state:
      - On entry, a timed transition is scheduled so that if no lick occurs within v.reward_timer_duration,
        the task goes to intertrial.
      - A lick during this window triggers reward delivery and transitions immediately to intertrial.
    """
    if event == 'entry':
        timed_goto_state('intertrial', v.reward_timer_duration)
    elif event == 'lick':
        hw.reward.release()
        v.reward_count += 1
        print("{}, reward number".format(v.reward_count))
        hw.speaker.off()
        goto_state('intertrial')
    elif event == 'session_timer':
        stop_framework()

def intertrial(event):
    """
    In the intertrial state:
      - On entry, the speaker is turned off.
      - In fixed mode, a timed transition returns the task to trial after v.IT_duration.
      - In baseline mode, the state monitors cursor_update events and transitions to trial once
        the frequency falls within the predefined baseline range.
    """
    if event == 'entry':
        hw.speaker.off()
        if v.IT_mode == "fixed":
            timed_goto_state('trial', v.IT_duration)
    elif event == 'cursor_update':
        if v.IT_mode == "baseline":
            freq = hw.bci_link.spk
            if freq is None:
                freq = v.freq_bins[5]
            if v.baseline_freq_range[0] <= freq <= v.baseline_freq_range[1]:
                print("baseline frequency detected, returning to trial")
                goto_state('trial')
    elif event == 'session_timer':
        stop_framework()

def all_states(event):
    if event == 'session_timer':
        stop_framework()

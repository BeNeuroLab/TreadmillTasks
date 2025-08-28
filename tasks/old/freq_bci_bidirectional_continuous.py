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
    'cursor_update',  # Event triggered by receiving BCI data (-1, 0, 1)
    'lick',
    'motion'
]

initial_state = 'intertrial' # Start in intertrial to shuffle first block

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
v.session_duration = 45 * minute
v.reward_duration = 50 * ms
v.hold_duration = 10 * ms  # Hold period at target index before reward state
v.trial_duration = 10 * second  # Maximum trial duration if target not reached
v.IT_duration = 4 * second  # Intertrial interval duration
v.reward_timer_duration = 2 * second # Max duration in reward state waiting for lick
v.stimulus_duration = 1 * second # Duration of stimulus presentation (not used in this task)
# List of discrete frequency values the cursor can represent
v.freq_bins = [2181, 2594, 3084, 3668, 4362, 5187, 6169, 7336, 8724, 10375, 12338]
v.leds = [2, 4] # LED pins corresponding to [low_target, high_target]

# --- Trial Structure Variables ---
v.trial_types = ['low_target', 'high_target'] # Types of trials
v.trial_type = v.trial_types[0] # Current trial type
# Force shuffle before the first trial starts
v.trial_in_block = len(v.trial_types)
v.target_idx = 0 # Index of the target frequency bin (0 or max)
#v.trial_in_block = len(v.trial_types) # Start >= block size to force shuffle on first ITI entry
v.correct_trials = 0
v.total_trials = 0
# --------------------------------

v.reward_count = 0 # Keep track of total rewards delivered
v.change_state = True
v.trial_state = 0
v.IT_mode                = "baseline"        # "fixed" or "baseline"

# -------------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------------
def shuffle_list(lst): # Fisher-Yates Shuffle
#    """Shuffles a list in place."""
   for i in range(len(lst) - 1, 0, -1):
       j = randint(0, i)
       lst[i], lst[j] = lst[j], lst[i]  # Swap elements


# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(10)
    utime.sleep_ms(20)
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    hw.speaker.off() # Start with speaker off
    hw.light.all_off() # Ensure lights are off
    set_timer('session_timer', v.session_duration, True) # Ensure session termination

    print('{}, Task Started.'.format(get_current_time()))
    # ------------------------

    print('{}, before_camera_trigger'.format(get_current_time()))
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    hw.cameraTrigger.start()

def run_end():
    hw.reward.stop()
    hw.speaker.off()
    hw.light.all_off()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.off()
    print('{}, Run End. Correct Trials: {}/{}, Total Rewards: {}'.format(
        get_current_time(), v.correct_trials, v.total_trials, v.reward_count))

# -------------------------------------------------------------------------
# States
# -------------------------------------------------------------------------
def trial(event):
    """
    Trial state:
      - Determines trial type (low/high target), sets target index, turns on cue LED.
      - Resets frequency index to middle, turns speaker on.
      - Monitors BCI control to see if target index is reached.
      - Times out to intertrial if target not reached within v.trial_duration.
    """
    if event == 'entry':
        v.total_trials += 1
        # v.trial_type = choice(v.trial_types)
        v.trial_type = v.trial_types[v.trial_in_block]
        v.trial_state = 1
        if v.change_state:
            hw.bci_link.send_int(v.trial_state)
            v.change_state = False
            v.trial_in_block += 1

        if v.trial_type == 'low_target':
            v.target_idx = 0
            target_led = v.leds[0]
        else: # 'high_target'
            v.target_idx = len(v.freq_bins) - 1
            target_led = v.leds[1]

        hw.light.cue(target_led) # Turn on the target cue LED

        print("{}, Trial #{} Start. Type: {}, Target Index: {}, Cue LED: {}".format(
            get_current_time(), v.total_trials, v.trial_type, v.target_idx, target_led))

        # Automatically move to intertrial after trial_duration if target not reached.
        timed_goto_state('intertrial', v.trial_duration)

    elif event == 'cursor_update':

        freq = hw.bci_link.spk
        if freq is None:
            freq = v.freq_bins[5]  # Default to a mid-range frequency
        print("{}, spk_frequency".format(freq))
        hw.speaker.sine(freq)

        # Check if the BCI-controlled index has reached the target for THIS trial.
        if freq == v.target_idx:
            print("{}, Target Index Reached: {}".format(get_current_time(), v.current_freq_idx))
            goto_state('threshold_crossed') # Moving state implicitly cancels trial timeout timer

def threshold_crossed(event):
    """
    Correct target index reached by BCI.
      - Enters hold period. Allows cursor updates (which will reset to trial).
      - Licks during hold are ignored.
      - If hold completes without cursor update, moves to reward state.
    """
    if event == 'entry':
        print("{}, Target Reached ({}), Entering Hold ({:.1f}ms)".format(
            get_current_time(), v.trial_type, v.hold_duration))
        
        # Start hold timer, go to reward state if timer completes.
        timed_goto_state('reward', v.hold_duration)

    elif event == 'cursor_update':
        # Any BCI update during hold resets the trial (enforces holding at target)
        print("{}, Cursor Updated During Hold, Resetting to Trial".format(get_current_time()))
        goto_state('trial') # Moving state implicitly cancels timed_goto_state('reward', ...)

def reward(event):
    """
    Ready to reward state (hold period completed successfully).
      - Start timer; if no lick occurs, go to intertrial (counts as missed opportunity).
      - A lick triggers reward, increments counters, and transitions to intertrial.
    """
    if event == 'entry':
        print("{}, Entering Reward Window (Waiting for Lick, Timeout: {:.1f}s)".format(
            get_current_time(), v.reward_timer_duration / second))
        # Wait for lick, timeout to intertrial if no lick.
        timed_goto_state('intertrial', v.reward_timer_duration)
    elif event == 'lick':
        hw.reward.release()
        v.reward_count += 1 # Increment total rewards
        v.correct_trials += 1 # Increment correct trials for this block structure
        #v.trial_in_block += 1 # Advance to next trial in block
        print("{}, Lick Detected! Reward #{} Delivered. Correct Trials: {}/{}. Advancing block.".format(
              get_current_time(), v.reward_count, v.correct_trials, v.total_trials))
        timed_goto_state('intertrial', v.stimulus_duration) # Moving state implicitly cancels reward window timeout

def intertrial(event):
    """
    Intertrial interval.
      - Turns off speaker and lights.
      - Starts fixed timer to transition back to trial.
    """
    if event == 'entry':

        v.trial_state = 0
        hw.bci_link.send_int(v.trial_state)
        v.change_state = True

        hw.speaker.off() # Ensure speaker is off
        hw.light.all_off() # Ensure lights are off

        # Check if block ended, shuffle if necessary
        if v.trial_in_block >= len(v.trial_types):
           v.trial_in_block = 0
           shuffle_list(v.trial_types)

        print("{}, Entering Intertrial State (Duration: {:.1f}s)".format(
            get_current_time(), v.IT_duration / second))
        
        if v.IT_mode == "fixed":
            timed_goto_state('trial', v.IT_duration)

    elif event == 'cursor_update':

        if v.IT_mode == "baseline":
            freq = hw.bci_link.spk
            if freq is None:
                freq = v.freq_bins[5]
            if v.baseline_freq_range[0] <= freq <= v.baseline_freq_range[1]:
                print("baseline_frequency_detected_returning_to_trial")
                timed_goto_state('trial', v.IT_duration)

# -------------------------------------------------------------------------
# Event-handling functions
# -------------------------------------------------------------------------

def all_states(event):
    """
    Executed before state-specific code. Handles session timer.
    """
    if event == 'session_timer':
        print('{}, Session Timer Expired'.format(get_current_time()))
        stop_framework() # End the experiment
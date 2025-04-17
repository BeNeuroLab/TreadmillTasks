import utime
from pyControl.utility import *
import hardware_definition as hw
from devices import *
import random # Added for shuffling trial types

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
v.reward_duration = 40 * ms
v.hold_duration = 10 * ms  # Hold period at target index before reward state
v.trial_duration = 10 * second  # Maximum trial duration if target not reached
v.IT_duration = 4 * second  # Intertrial interval duration
v.reward_timer_duration = 2 * second # Max duration in reward state waiting for lick
v.stimulus_duration = 2 * second # Duration of stimulus presentation (not used in this task)
# List of discrete frequency values the cursor can represent
v.freq_bins = [2181, 2594, 3084, 3668, 4362, 5187, 6169, 7336, 8724, 10375, 12338]
v.leds = [2, 4] # LED pins corresponding to [low_target, high_target]

# --- Trial Structure Variables ---
v.trial_types = ['low_target', 'high_target'] # Types of trials
v.trial_type = v.trial_types[0] # Current trial type
v.target_idx = 0 # Index of the target frequency bin (0 or max)
#v.trial_in_block = len(v.trial_types) # Start >= block size to force shuffle on first ITI entry
v.correct_trials = 0
v.total_trials = 0
# --------------------------------

v.reward_count = 0 # Keep track of total rewards delivered

# --- Variable for index-based control ---
v.current_freq_idx = 0
# --- Flag to control when cursor updates affect index/speaker ---
v.accept_cursor_updates = True
# -------------------------------------------------------------

# -------------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------------
#def shuffle_list(lst): # Fisher-Yates Shuffle
##    """Shuffles a list in place."""
#    for i in range(len(lst) - 1, 0, -1):
#        j = random.randint(0, i)
#        lst[i], lst[j] = lst[j], lst[i]  # Swap elements

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

    # --- Initialize index and trial counters ---
    v.current_freq_idx = len(v.freq_bins) // 2 # Set initial index (will be reset on trial entry)
    v.accept_cursor_updates = False # Start in intertrial where updates are initially ignored
    v.correct_trials = 0
    v.total_trials = 0
    # Force shuffle before the first trial starts
    #v.trial_in_block = len(v.trial_types)
    print('{}, Task Started. Initial Freq Index: {}'.format(get_current_time(), v.current_freq_idx))
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
      - Allows cursor updates.
      - Monitors BCI control to see if target index is reached.
      - Times out to intertrial if target not reached within v.trial_duration.
    """
    if event == 'entry':
        v.total_trials += 1
        # Determine trial type and set target index/LED
        #v.trial_type = v.trial_types[v.trial_in_block]
        v.trial_type = random.choice(v.trial_types)
        if v.trial_type == 'low_target':
            v.target_idx = 0
            target_led = v.leds[0]
        else: # 'high_target'
            v.target_idx = len(v.freq_bins) - 1
            target_led = v.leds[1]

        hw.light.cue(target_led) # Turn on the target cue LED

        # Allow cursor updates to affect index/speaker in this state
        v.accept_cursor_updates = True
        # Reset frequency index to the middle bin
        v.current_freq_idx = len(v.freq_bins) // 2
        middle_freq = v.freq_bins[v.current_freq_idx]
        # Start speaker playing the middle frequency
        hw.speaker.sine(middle_freq)
        print("{}, Trial #{} Start. Type: {}, Target Index: {}, Cue LED: {}. Freq Index RESET to: {}".format(
            get_current_time(), v.total_trials, v.trial_type, v.target_idx, target_led, v.current_freq_idx))

        # Automatically move to intertrial after trial_duration if target not reached.
        timed_goto_state('intertrial', v.trial_duration)

    elif event == 'cursor_update':
        # Check performed only if v.accept_cursor_updates is True (handled in all_states)
        # Check if the BCI-controlled index has reached the target for THIS trial.
        if v.current_freq_idx == v.target_idx:
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
        # Allow cursor updates (will reset to trial if BCI moves away from target)
        v.accept_cursor_updates = True
        print("{}, Target Reached ({}), Entering Hold ({:.1f}ms)".format(
            get_current_time(), v.trial_type, v.hold_duration))
        # Start hold timer, go to reward state if timer completes.
        timed_goto_state('reward', v.hold_duration)
    elif event == 'lick':
        print("{}, Lick ignored during target hold period".format(get_current_time()))
        pass # Ignore licks during hold
    elif event == 'cursor_update':
        # Any BCI update during hold resets the trial (enforces holding at target)
        print("{}, Cursor Updated During Hold, Resetting to Trial".format(get_current_time()))
        goto_state('trial') # Moving state implicitly cancels timed_goto_state('reward', ...)

def reward(event):
    """
    Ready to reward state (hold period completed successfully).
      - Disallow cursor updates.
      - Start timer; if no lick occurs, go to intertrial (counts as missed opportunity).
      - A lick triggers reward, increments counters, and transitions to intertrial.
    """
    if event == 'entry':
        # Disallow cursor updates from affecting index/speaker in this state
        v.accept_cursor_updates = False
        # Turn off cue light as target was held successfully
        hw.light.all_off()
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
        hw.speaker.off() # Turn off speaker after successful reward
        timed_goto_state('intertrial', v.stimulus_duration) # Moving state implicitly cancels reward window timeout

def intertrial(event):
    """
    Intertrial interval.
      - Turns off speaker and lights.
      - Shuffles trial types if end of block reached.
      - Disallows cursor updates.
      - Starts fixed timer to transition back to trial.
    """
    if event == 'entry':
        # Disallow cursor updates from affecting index/speaker in this state
        v.accept_cursor_updates = False
        hw.speaker.off() # Ensure speaker is off
        hw.light.all_off() # Ensure lights are off

        # Check if block ended, shuffle if necessary
        #if v.trial_in_block >= len(v.trial_types):
         #   print("{}, End of Block Reached. Shuffling trial types.".format(get_current_time()))
        #    v.trial_in_block = 0
         #   shuffle_list(v.trial_types)
         #   print("{}, Next Block Order: {}".format(get_current_time(), v.trial_types))

        print("{}, Entering Intertrial State (Duration: {:.1f}s)".format(
            get_current_time(), v.IT_duration / second))
        # Always use a fixed ITI duration.
        timed_goto_state('trial', v.IT_duration)

# -------------------------------------------------------------------------
# Event-handling functions
# -------------------------------------------------------------------------

def all_states(event):
    """
    Executed before state-specific code. Handles session timer and cursor updates (if allowed by flag).
    """
    if event == 'cursor_update':
        # Only process the update if the current state allows it
        if v.accept_cursor_updates:
            # Read the index change instruction (-1, 0, 1)
            idx_change_instruction = hw.bci_link.spk

            # Handle potential None value from BCI link (treat as 0 change)
            if idx_change_instruction is None:
                idx_change_instruction = 0
                # print("{}, WARNING: Received None from BCI link, treating as 0 change.".format(get_current_time())) # Optional Warning

            # Map incoming value 2 to -1 if necessary (from previous script version)
            if idx_change_instruction == 2:
                idx_change_instruction = -1

            if idx_change_instruction in [-1, 0, 1]:
                if idx_change_instruction != 0:
                    # Calculate the potential new index
                    potential_new_idx = v.current_freq_idx + idx_change_instruction
                    # Clamp the index
                    new_idx = max(0, min(len(v.freq_bins) - 1, potential_new_idx))
                    # Update index and speaker if changed
                    if new_idx != v.current_freq_idx:
                        v.current_freq_idx = new_idx
                        current_freq = v.freq_bins[v.current_freq_idx]
                        hw.speaker.sine(current_freq)
                        # Print update only if index actually changed
                        print('{}, BCI Instr: {}, New Idx: {}, New Freq: {:.0f} Hz'.format(
                            get_current_time(), idx_change_instruction, v.current_freq_idx, current_freq))
                    else: # At boundary, instruction tried to push further
                         current_freq = v.freq_bins[v.current_freq_idx]
                         hw.speaker.sine(current_freq) # Still update speaker
                         # Optional: print('{}, BCI Instr: {}, At Boundary (Idx: {}), Freq: {:.0f} Hz'.format(
                         #    get_current_time(), idx_change_instruction, v.current_freq_idx, current_freq))
                else: # Instruction is 0 (stay)
                     current_freq = v.freq_bins[v.current_freq_idx]
                     hw.speaker.sine(current_freq) # Ensure speaker plays current freq
                     # Optional: print('{}, BCI Instr: 0 (Stay), Idx: {}, Freq: {:.0f} Hz'.format(
                     #    get_current_time(), v.current_freq_idx, current_freq))
            else: # Unexpected BCI value
                print('{}, ERROR: Unexpected BCI instruction received: {}'.format(get_current_time(), idx_change_instruction))
        # else: v.accept_cursor_updates is False, ignore the cursor update for index/speaker changes.

    elif event == 'session_timer':
        print('{}, Session Timer Expired'.format(get_current_time()))
        stop_framework() # End the experiment
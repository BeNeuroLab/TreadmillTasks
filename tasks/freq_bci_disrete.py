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
    'lick'
]

initial_state = 'trial'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
v.session_duration = 60 * minute
v.reward_duration = 40 * ms
v.hold_duration = 120 * ms  # Hold period in threshold_crossed before moving to reward
v.trial_duration = 10 * second  # Maximum trial duration if no threshold is crossed
v.IT_duration = 3 * second  # Intertrial interval duration
v.reward_timer_duration = 2 * second  # Maximum duration in the reward state waiting for a lick

# List of discrete frequency values the cursor can represent
v.freq_bins = [2181, 2594, 3084, 3668, 4362, 5187, 6169, 7336, 8724, 10375, 12338]

v.reward_count = 0

# --- Variable for index-based control ---
# Current index in the v.freq_bins list
v.current_freq_idx = 0
# --- Flag to control when cursor updates affect index/speaker ---
v.accept_cursor_updates = True
# -------------------------------------------------------------

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(8)
    utime.sleep_ms(20)
    hw.reward.reward_duration = v.reward_duration
    hw.speaker.off() # Start with speaker off
    set_timer('session_timer', v.session_duration, True) # Ensure session termination

    # --- Initialize index ---
    # Set initial index for the very first trial start (will be reset on subsequent trials)
    v.current_freq_idx = len(v.freq_bins) // 2
    # Set initial state for accepting cursor updates
    v.accept_cursor_updates = True # Start in trial state where updates are accepted
    print('{}, Initial Freq Index Set To: {}'.format(get_current_time(), v.current_freq_idx))
    # ------------------------

    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

def run_end():
    hw.reward.stop()
    hw.speaker.off()
    hw.cameraTrigger.stop()
    hw.off()
    print('{}, Run End. Total Rewards: {}'.format(get_current_time(), v.reward_count))


# -------------------------------------------------------------------------
# States
# -------------------------------------------------------------------------
def trial(event):
    """
    In the trial state:
      - On entry, reset freq index to middle, turn speaker on, allow cursor updates, start max trial timer.
      - On cursor_update (handled in all_states), the index is updated.
        If the index reaches either boundary (0 or max), transition to threshold_crossed.
      - Speaker plays the tone corresponding to the current index during updates.
    """
    if event == 'entry':
        # Allow cursor updates to affect index/speaker in this state
        v.accept_cursor_updates = True
        # Reset frequency index to the middle bin
        v.current_freq_idx = len(v.freq_bins) // 2
        middle_freq = v.freq_bins[v.current_freq_idx]
        # Start speaker playing the middle frequency
        hw.speaker.sine(middle_freq)
        print("{}, Entering Trial State, Index RESET to: {}, Freq: {:.0f} Hz (Accepting Updates)".format(
            get_current_time(), v.current_freq_idx, middle_freq))

        # Automatically move to intertrial after trial_duration if no threshold crossing.
        timed_goto_state('intertrial', v.trial_duration)

    elif event == 'cursor_update':
        # Check performed only if v.accept_cursor_updates is True (handled in all_states)
        # Check if the current index is at a boundary.
        is_at_boundary = (v.current_freq_idx == 0 or
                          v.current_freq_idx == len(v.freq_bins) - 1)
        if is_at_boundary:
            print("{}, Boundary Index Reached: {}".format(get_current_time(), v.current_freq_idx))
            goto_state('threshold_crossed') # Moving state implicitly cancels timed_goto_state('intertrial',...)

def threshold_crossed(event):
    """
    Threshold index reached.
      - On entry, allow cursor updates (to reset trial), start hold timer.
      - Licks during hold are ignored.
      - Any cursor_update during hold resets back to trial state (handled in all_states logic).
    """
    if event == 'entry':
        # Allow cursor updates to affect index/speaker (specifically to trigger reset to trial)
        v.accept_cursor_updates = True
        print("{}, Entering Threshold Crossed State (Index: {}), Holding for {:.1f}ms (Accepting Updates)".format(
            get_current_time(), v.current_freq_idx, v.hold_duration))
        # Start hold timer, go to reward if timer completes.
        timed_goto_state('reward', v.hold_duration)
    elif event == 'lick':
        print("{}, Lick ignored during hold period".format(get_current_time()))
        pass # Ignore licks during hold
    elif event == 'cursor_update':
        # Any BCI update during hold resets the trial.
        # Logic executed only if v.accept_cursor_updates is True
        print("{}, Cursor Updated During Hold, Resetting to Trial".format(get_current_time()))
        goto_state('trial') # Moving state implicitly cancels timed_goto_state('reward', ...)
    # Removed 'exit' handler - implicit cancellation by goto_state is sufficient

def reward(event):
    """
    Ready to reward state (hold period completed).
      - On entry, disallow cursor updates, start timeout timer.
      - A lick triggers reward delivery and immediate transition to intertrial.
    """
    if event == 'entry':
        # Disallow cursor updates from affecting index/speaker in this state
        v.accept_cursor_updates = False
        print("{}, Entering Reward State (Waiting for Lick, Timeout: {:.1f}s) (Ignoring Updates)".format(
            get_current_time(), v.reward_timer_duration / second))
        # Wait for lick, timeout to intertrial if no lick.
        timed_goto_state('intertrial', v.reward_timer_duration)
    elif event == 'lick':
        hw.reward.release()
        v.reward_count += 1
        print("{}, Lick Detected, Reward #{} Delivered".format(get_current_time(), v.reward_count))
        hw.speaker.off() # Turn off speaker after successful reward
        goto_state('intertrial') # Moving state implicitly cancels timed_goto_state('intertrial', ...)
    # Removed 'exit' handler - implicit cancellation by goto_state is sufficient

def intertrial(event):
    """
    Intertrial interval.
      - On entry, speaker off, disallow cursor updates, start fixed timer.
    """
    if event == 'entry':
         # Disallow cursor updates from affecting index/speaker in this state
        v.accept_cursor_updates = False
        hw.speaker.off() # Ensure speaker is off
        print("{}, Entering Intertrial State (Duration: {:.1f}s) (Ignoring Updates)".format(
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
                        print('{}, BCI Instr: {}, New Idx: {}, New Freq: {:.0f} Hz'.format(
                            get_current_time(), idx_change_instruction, v.current_freq_idx, current_freq))
                    else: # At boundary
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
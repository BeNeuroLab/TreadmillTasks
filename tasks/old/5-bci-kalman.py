import utime
from pyControl.utility import *
import hardware_definition as hw
from devices import *

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'intertrial',
    'cue_period', # New state for the initial cue
    'trial',
    'threshold_crossed',
    'reward'
]

events = [
    'session_timer',
    'cursor_update',  # Event triggered by receiving BCI data (frequency value)
    'lick',
    'motion'
]

initial_state = 'intertrial' # Start in intertrial

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
v.session_duration = 45 * minute
v.reward_duration = 50 * ms
v.hold_duration = 10 * ms  # Hold period at target frequency before reward state
v.trial_duration = 10 * second  # Maximum trial duration (BCI component) if target not reached
v.cue_duration = 1 * second # Duration of the initial cue period
v.IT_duration = 4 * second  # Intertrial interval duration
v.reward_timer_duration = 2 * second # Max duration in reward state waiting for lick
v.stimulus_duration = 1 * second # Duration of stimulus presentation after reward delivery

# List of discrete frequency values the cursor can represent
v.freq_bins = [2181, 2594, 3084, 3668, 4362, 5187, 6169, 7336, 8724, 10375, 12338]
v.led_pin = 4 # Single LED pin for the high target
v.target_freq = v.freq_bins[-1] # The target frequency value
v.baseline_freq = v.freq_bins[8]

# --- Trial Structure Variables ---
# Removed trial_types, trial_type, trial_in_block as there's only one type now.
v.correct_trials = 0
v.total_trials = 0
# --------------------------------

v.reward_count = 0 # Keep track of total rewards delivered
v.bci_state_change_pending = True # Flag to send BCI state update
v.bci_active_state = 0 # 0: inactive, 1: active/trial
v.IT_mode = "baseline"        # "fixed" or "baseline"

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
    # Ensure BCI link is notified that control is off
    hw.bci_link.send_int(0) # Send inactive state
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

def intertrial(event):
    """
    Intertrial interval.
      - Turns off speaker and lights.
      - Sends inactive state (0) to BCI link.
      - Starts timer to transition to the cue period.
    """
    if event == 'entry':

        hw.bci_link.send_int(0)
        v.bci_state_change_pending = True # Ready to send 'active' on next trial start

        hw.speaker.off() # Ensure speaker is off
        hw.light.all_off() # Ensure lights are off

        print("{}, Entering Intertrial State (Duration: {:.1f}s)".format(
            get_current_time(), v.IT_duration / second))

        if v.IT_mode == "fixed":
            timed_goto_state('cue_period', v.IT_duration)

    elif event == 'cursor_update':

        if v.IT_mode == "baseline":
            freq = hw.bci_link.spk
            if freq is None:
                freq = v.freq_bins[5]
            if freq <= v.baseline_freq:
                print("baseline_frequency_detected_returning_to_trial")
                timed_goto_state('cue_period', v.IT_duration)

def cue_period(event):
    """
    Cue Period State:
      - Turns on the target cue LED.
      - Plays the target frequency for a fixed duration.
      - Transitions to the main 'trial' state afterwards.
      - BCI control is NOT active during this state.
    """
    if event == 'entry':
        v.total_trials += 1
        hw.bci_link.send_int(1)
        print("{}, Trial #{} Start. Cue Period (Duration: {:.1f}s)".format(
            get_current_time(), v.total_trials, v.cue_duration / second))

        # Play the target frequency
        print("{}, Playing Cue Frequency: {}".format(get_current_time(), v.target_freq))
        hw.speaker.sine(v.target_freq)

        # Transition to the trial state after the cue duration
        timed_goto_state('trial', v.cue_duration)

def trial(event):
    """
    Trial state (BCI Control Active):
      - Cue LED remains on.
      - Speaker starts responding to BCI frequency input.
      - Notifies BCI link that the trial (active control period) has started.
      - Monitors BCI control to see if target frequency is reached.
      - Times out to intertrial if target not reached within v.trial_duration.
    """
    if event == 'entry':

        hw.speaker.off()

         # Activate BCI control period
        if v.bci_state_change_pending:
            hw.bci_link.send_int(2)
            v.bci_state_change_pending = False # State sent
            print("{}, BCI Control Enabled (State=1 Sent)".format(get_current_time()))

        hw.light.cue(v.led_pin) # Turn on the target cue LED
        hw.speaker.sine(v.baseline_freq)

        print("{}, BCI Active Trial Period Started (Max Duration: {:.1f}s)".format(
            get_current_time(), v.trial_duration / second))

        # Automatically move to intertrial after trial_duration if target not reached.
        # The cue period timer is implicitly cancelled by entering this state.
        timed_goto_state('intertrial', v.trial_duration)

        # Note: Speaker should ideally update immediately based on first BCI input.
        # If no input received yet, it might continue playing the cue frequency briefly.
        # Or, set speaker to a neutral frequency or off briefly if desired,
        # but the current logic will let cursor_update handle the first change.


    elif event == 'cursor_update':
        # Get the frequency command from the BCI link
        freq_command = hw.bci_link.spk

        # Ensure frequency is within the defined bins (optional, good practice)
        # This step depends on whether hw.bci_link.spk provides exact bin frequencies
        # or continuous values that need snapping. Assuming it provides exact bin frequencies.
        
        if freq_command is not None:
            print("{}, Cursor Update Received. Freq: {}".format(get_current_time(), freq_command))
            hw.speaker.sine(freq_command)

        # Check if the BCI-controlled frequency matches the target frequency.
        # IMPORTANT: Comparing frequency values now, not index.
        if freq_command == v.target_freq:
            print("{}, Target Frequency Reached: {}".format(get_current_time(), freq_command))
            goto_state('threshold_crossed') # Moving state implicitly cancels trial timeout timer

def threshold_crossed(event):
    """
    Target frequency reached by BCI.
      - Enters hold period. Speaker continues playing target frequency. LED stays on.
      - BCI updates during hold reset the trial (go back to 'trial' state).
      - If hold completes without BCI update causing frequency change, moves to reward state.
    """
    if event == 'entry':
        print("{}, Target Freq Reached ({}), Entering Hold ({:.1f}ms)".format(
            get_current_time(), v.target_freq, v.hold_duration))

        # Start hold timer, go to reward state if timer completes.
        timed_goto_state('reward', v.hold_duration)

    elif event == 'cursor_update':
        # Check if the BCI update changes the frequency *away* from the target
        freq_command = hw.bci_link.spk
        if freq_command is not None and freq_command != v.target_freq:
            print("{}, Cursor Updated During Hold (Freq: {}), Resetting to Trial".format(get_current_time(), freq_command))
            goto_state('trial') # Moving state implicitly cancels timed_goto_state('reward', ...)
        # If freq_command is None or still the target_freq, ignore and let hold timer continue.


def reward(event):
    """
    Ready to reward state (hold period completed successfully).
      - Speaker and LED turned off upon entering reward window.
      - BCI link notified that control period is over (state=0).
      - Start timer; if no lick occurs, go to intertrial.
      - A lick triggers reward delivery, increments counters, and transitions to intertrial.
    """
    if event == 'entry':

        hw.bci_link.send_int(3)

        print("{}, Entering Reward Window (Waiting for Lick, Timeout: {:.1f}s)".format(
            get_current_time(), v.reward_timer_duration / second))
        # Wait for lick, timeout to intertrial if no lick.
        timed_goto_state('intertrial', v.reward_timer_duration) # Timer starts *after* setup above

    elif event == 'lick':
        hw.reward.release()
        v.reward_count += 1 # Increment total rewards
        v.correct_trials += 1 # Increment correct trials
        print("{}, Lick Detected! Reward #{} Delivered. Correct Trials: {}/{}. Going to ITI.".format(
              get_current_time(), v.reward_count, v.correct_trials, v.total_trials))
        timed_goto_state('intertrial', v.stimulus_duration) # Moving state implicitly cancels reward window timeout

# -------------------------------------------------------------------------
# Event-handling functions
# -------------------------------------------------------------------------

def all_states(event):
    """
    Executed before state-specific code. Handles session timer and motion.
    """
    # Handle session timer globally
    if event == 'session_timer':
        print('{}, Session Timer Expired'.format(get_current_time()))
        stop_framework() # End the experiment

    # Optional: Handle motion detection globally or within specific states if needed
    # if event == 'motion':
    #     print('{}, Motion Detected'.format(get_current_time()))
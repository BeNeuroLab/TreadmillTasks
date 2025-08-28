from pyControl.utility import *
import hardware_definition as hw
from devices import *
import random

# -------------------------------------------------------------------------
# States for Passive Presentation
states = ['intertrial', 'stimulus_presentation']

# Events for Passive Presentation
events = ['session_timer', 'stimulus_timer', 'motion'] # Kept motion for potential logging

# Initial state
initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables
v.session_duration = 20 * minute # Increased session timer as block limit is primary stop
v.stimulus_duration = 1 * second  # Fixed duration for each stimulus presentation
v.iti_duration = 1 * second     # Inter-trial interval

# Speaker Frequencies
v.spk_freqs = [2181, 2594, 3084, 3668, 4362, 5187, 6169, 7336, 8724, 10375, 12338] # Example frequencies

# LED Definitions
v.led_config_left = 'left_led'
v.led_config_right = 'right_led'
v.led_indices_left = [2]  # The actual hardware index for left LED(s)
v.led_indices_right = [4] # The actual hardware index for right LED(s)

# Trial Tracking & Block Control
v.trial_in_block = 0      # Track position within the block
v.total_trials = 0        # Count total trials presented
v.block_size = 0          # Will be calculated by build_trial_block
v.trial_combinations = [] # Holds the shuffled combinations for the current block
v.master_stimulus_list = [] # Holds all unique stimuli in fixed order for ID mapping
v.max_blocks = 10         # <--- Set the desired number of blocks here
v.completed_blocks = 0    # Counter for completed blocks

# -------------------------------------------------------------------------

def shuffle_list(lst): # Fisher-Yates Shuffle
    """Shuffles a list in place."""
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i] # Swap elements

# -------------------------------------------------------------------------

def generate_all_combinations():
    """
    Generates a list of all unique stimulus combinations in a fixed order.
    This is used for assigning consistent TypeIDs.
    """
    combinations = []
    # Order: Silence, LED Left, LED Right, Freqs, Freqs+Left, Freqs+Right
    combinations.append((None, None)) # TypeID 0
    combinations.append((v.led_config_left, None)) # TypeID 1
    combinations.append((v.led_config_right, None)) # TypeID 2
    start_freq_id = len(combinations)

    # Frequencies only
    for i, freq in enumerate(v.spk_freqs):
        combinations.append((None, freq)) # TypeID 3, 6, 9, ...

    # Frequencies + Left LED
    for i, freq in enumerate(v.spk_freqs):
        combinations.append((v.led_config_left, freq)) # TypeID 4, 7, 10, ...

    # Frequencies + Right LED
    for i, freq in enumerate(v.spk_freqs):
        combinations.append((v.led_config_right, freq)) # TypeID 5, 8, 11, ...

    return combinations

# -------------------------------------------------------------------------

def build_trial_block():
    """
    Constructs a block containing exactly one presentation of each unique
    stimulus combination, retrieved from the master list, and then shuffles it.
    """
    # Use the master list to ensure all combinations are included
    current_block_combinations = list(v.master_stimulus_list)
    shuffle_list(current_block_combinations) # Randomize the order for this block
    v.block_size = len(current_block_combinations)
    # print(f"Generated new block with {v.block_size} unique stimulus combinations.")
    return current_block_combinations

# -------------------------------------------------------------------------

def run_start():
    """
    Called once at the start of the framework.
    Initializes hardware, variables, generates master list, and starts the first trial block.
    """
    hw.speaker.set_volume(10) # Set desired speaker volume
    hw.cameraTrigger.start()
    hw.light.all_off()
    hw.motionSensor.record() # Keep motion recording if needed
    hw.motionSensor.threshold = 10 # Example threshold

    # Generate the master list of stimuli for consistent ID mapping
    v.master_stimulus_list = generate_all_combinations()
    # print(f"Master stimulus list generated with {len(v.master_stimulus_list)} unique types.")

    # Initialize counters
    v.total_trials = 0
    v.trial_in_block = 0
    v.completed_blocks = 0

    # Build the first block
    v.trial_combinations = build_trial_block()

    set_timer('session_timer', v.session_duration) # Keep session timer as a backup
    print('{}, Session Started. Target Blocks: {}. CPI: {}'.format(
          get_current_time(), v.max_blocks, hw.motionSensor.sensor_x.CPI))
    hw.cameraTrigger.start() # Ensure camera trigger is running

def run_end():
    """
    Called once at the end of the framework.
    Turns off hardware and prints final summary.
    """
    hw.speaker.off()
    hw.light.all_off()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    print('{}, Session Ended. Blocks Completed: {}. Total trials presented: {}'.format(
          get_current_time(), v.completed_blocks, v.total_trials))

# -------------------------------------------------------------------------
# State behaviour
# -------------------------------------------------------------------------

def intertrial(event):
    """
    Handles the inter-trial interval.
    Ensures stimuli are off, checks for block completion and max blocks, times the ITI.
    """
    if event == 'entry':
        # Ensure all stimuli are off
        hw.speaker.off()
        hw.light.all_off()
        # print('{}, ITI Started'.format(get_current_time())) # Less verbose logging

        # Check if the current block is finished
        if v.trial_in_block >= v.block_size:
            v.completed_blocks += 1
            print('{}, Block {} completed.'.format(get_current_time(), v.completed_blocks))

            # Check if max blocks reached
            if v.completed_blocks >= v.max_blocks:
                print('{}, Maximum blocks ({}) reached. Stopping framework.'.format(
                      get_current_time(), v.max_blocks))
                stop_framework()
                return # Exit event handler after stopping

            # Reset for next block if max not reached
            v.trial_in_block = 0
            v.trial_combinations = build_trial_block() # Generate the next shuffled block

        # Start the ITI timer (if framework hasn't stopped)
        timed_goto_state('stimulus_presentation', v.iti_duration)

    # Optional: Log motion during ITI if needed
    # elif event == 'motion':
    #     print('{}, Motion detected during ITI'.format(get_current_time()))


def stimulus_presentation(event):
    """
    Presents the selected stimulus combination for a fixed duration.
    """
    if event == 'entry':
        v.total_trials += 1
        # Get the current stimulus configuration for this trial
        current_stimulus = v.trial_combinations[v.trial_in_block]
        led_setting, freq_setting = current_stimulus

        # Find the unique TypeID using the master list
        try:
            trial_type_id = v.master_stimulus_list.index(current_stimulus)
        except ValueError:
            # This should not happen if master list is generated correctly
            trial_type_id = -1 # Error indicator
            print("Error: Current stimulus not found in master list!")

        # --- Updated Print Statement ---
        print('{}, Block: {}, Trial: {}/{}, TypeID: {}, Stimulus: {}'.format(
              get_current_time(),
              v.completed_blocks + 1, # Current Block Number
              v.trial_in_block + 1,   # Trial number within block
              v.block_size,           # Total trials in block
              trial_type_id,          # Unique identifier for this stimulus type
              current_stimulus))      # The actual stimulus (LED, Freq)
        # --- End Updated Print Statement ---

        # Configure LEDs
        if led_setting == v.led_config_left:
            hw.light.cue_array(v.led_indices_left)
            # print('  LED: Left ON') # Less verbose logging
        elif led_setting == v.led_config_right:
            hw.light.cue_array(v.led_indices_right)
            # print('  LED: Right ON') # Less verbose logging
        else: # Includes None (Silence or Freq only)
            hw.light.all_off()
            # print('  LED: OFF') # Less verbose logging

        # Configure Speaker
        if freq_setting is not None:
            hw.speaker.sine(freq_setting)
            # print(f'  Sound: {freq_setting} Hz ON') # Less verbose logging
        else: # Includes None (Silence or LED only)
            hw.speaker.off()
            # print('  Sound: OFF') # Less verbose logging

        # Set timer for stimulus duration
        set_timer('stimulus_timer', v.stimulus_duration)

    elif event == 'stimulus_timer':
        # Stimulus duration is over, turn off stimuli
        hw.speaker.off()
        hw.light.all_off()
        # print('{}, Stimulus OFF'.format(get_current_time())) # Less verbose logging

        # Increment trial counter for the block
        v.trial_in_block += 1

        # Transition back to intertrial interval
        goto_state('intertrial')

    # Optional: Log motion during stimulus presentation if needed
    # elif event == 'motion':
    #     print('{}, Motion detected during stimulus'.format(get_current_time()))


def all_states(event):
    """
    Generic event handler for events applicable in any state.
    """
    if event == 'session_timer':
        # Session duration reached (backup stop condition)
        print('{}, Session Timer Expired (Backup Stop)'.format(get_current_time()))
        stop_framework()
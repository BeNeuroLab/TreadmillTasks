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
v.session_duration = 45 * minute
v.stimulus_duration = 1 * second  # Fixed duration for each stimulus presentation
v.iti_duration = 1 * second     # Inter-trial interval

# Speaker Frequencies
v.spk_freqs = [2181, 2594, 3084, 3668, 4362, 5187, 6169, 7336, 8724, 10375, 12338] # Example frequencies

# LED Definitions (ensure these match your hardware_definition.py)
# Using descriptive names for clarity in the block builder
v.led_config_left = 'left_led'
v.led_config_right = 'right_led'
v.led_indices_left = [2]  # The actual hardware index for left LED(s)
v.led_indices_right = [4] # The actual hardware index for right LED(s)

# Trial Tracking
v.trial_in_block = 0      # Track position within the block
v.total_trials = 0        # Count total trials presented
v.block_size = 0          # Will be calculated by build_trial_block
v.trial_combinations = [] # Holds the shuffled combinations for the current block

# -------------------------------------------------------------------------

def shuffle_list(lst): # Fisher-Yates Shuffle (kept from original)
    """Shuffles a list in place."""
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i] # Swap elements

# -------------------------------------------------------------------------

def build_trial_block():
    """
    Constructs a block containing exactly one presentation of each unique
    stimulus combination:
    - Silence (None, None)
    - Left LED only (led_config_left, None)
    - Right LED only (led_config_right, None)
    - Each Frequency only (None, freq)
    - Each Frequency + Left LED (led_config_left, freq)
    - Each Frequency + Right LED (led_config_right, freq)
    The block is then shuffled.
    """
    combinations = []

    # 1. Silence
    combinations.append((None, None))

    # 2. LEDs only
    combinations.append((v.led_config_left, None))
    combinations.append((v.led_config_right, None))

    # 3. Frequencies only and Frequencies + LEDs
    for freq in v.spk_freqs:
        combinations.append((None, freq))              # Freq only
        combinations.append((v.led_config_left, freq)) # Freq + Left LED
        combinations.append((v.led_config_right, freq))# Freq + Right LED

    shuffle_list(combinations) # Randomize the order
    v.block_size = len(combinations)
    # print(f"Generated new block with {v.block_size} unique stimulus combinations.")
    return combinations

# -------------------------------------------------------------------------

def run_start():
    """
    Called once at the start of the framework.
    Initializes hardware, variables, and starts the first trial block.
    """
    hw.speaker.set_volume(10) # Set desired speaker volume
    hw.cameraTrigger.start()
    hw.light.all_off()
    hw.motionSensor.record() # Keep motion recording if needed
    hw.motionSensor.threshold = 10 # Example threshold

    v.total_trials = 0
    v.trial_in_block = 0
    v.trial_combinations = build_trial_block() # Build the first block

    set_timer('session_timer', v.session_duration)
    print('{}, Session Started. CPI: {}'.format(get_current_time(), hw.motionSensor.sensor_x.CPI))
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
    print('{}, Session Ended. Total trials presented: {}'.format(get_current_time(), v.total_trials))

# -------------------------------------------------------------------------
# State behaviour
# -------------------------------------------------------------------------

def intertrial(event):
    """
    Handles the inter-trial interval.
    Ensures stimuli are off, checks if a new block is needed, and times the ITI.
    """
    if event == 'entry':
        # Ensure all stimuli are off
        hw.speaker.off()
        hw.light.all_off()
        print('{}, ITI Started'.format(get_current_time()))

        # Check if the current block is finished
        if v.trial_in_block >= v.block_size:
            print('{}, Block Complete. Regenerating...'.format(get_current_time()))
            v.trial_in_block = 0
            v.trial_combinations = build_trial_block() # Generate the next shuffled block

        # Start the ITI timer
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

        print('{}, Trial: {}/{}, Stimulus: {}'.format(
              get_current_time(), v.trial_in_block + 1, v.block_size, current_stimulus))

        # Configure LEDs
        if led_setting == v.led_config_left:
            hw.light.cue_array(v.led_indices_left)
            print('  LED: Left ON')
        elif led_setting == v.led_config_right:
            hw.light.cue_array(v.led_indices_right)
            print('  LED: Right ON')
        else: # Includes None (Silence or Freq only)
            hw.light.all_off()
            print('  LED: OFF')

        # Configure Speaker
        if freq_setting is not None:
            hw.speaker.sine(freq_setting)
            print('{}, freq_setting'.format(0))
            # print(f'  Sound: {freq_setting} Hz ON')
        else: # Includes None (Silence or LED only)
            hw.speaker.off()
            print('  Sound: OFF')

        # Set timer for stimulus duration
        set_timer('stimulus_timer', v.stimulus_duration)

    elif event == 'stimulus_timer':
        # Stimulus duration is over, turn off stimuli
        hw.speaker.off()
        hw.light.all_off()
        print('{}, Stimulus OFF'.format(get_current_time()))

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
        # Session duration reached, stop the framework
        print('{}, Session Timer Expired'.format(get_current_time()))
        stop_framework()
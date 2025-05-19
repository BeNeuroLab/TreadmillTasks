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
    'motion',
    'cue_end',
    'it_end'       # Event triggered when the initial cue presentation ends
]

initial_state = 'intertrial' # Start in intertrial to shuffle first block

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
v.session_duration = 45 * minute
v.reward_duration = 60 * ms
v.hold_duration = 10 * ms  # Hold period at target index before reward state
v.baseline_hold = 10 * ms # Hold period of baseline period
v.trial_duration = 10 * second  # Maximum trial duration if target not reached
v.IT_duration = 4 * second  # Intertrial interval duration
v.reward_timer_duration = 2 * second # Max duration in reward state waiting for lick
v.stimulus_duration = 0.25 * second # Duration of stimulus presentation after rewarded lick
v.cue_duration = 1000 * ms # Duration for the initial target frequency cue
v.cue_active = False # Flag to indicate if the initial cue is currently playing
v.it_active = False # Flag to indicate if the IT period is active during baseline mode
v.baseline_hold_active = False

# List of discrete frequency values the cursor can represent
v.freq_bins = [2181, 2594, 3084, 3668, 4362, 5187, 6169, 7336, 8724, 10375, 12338]
v.baseline_freq_range = [2000,10000]
v.target_freq = 11000
# --- Trial Structure Variables ---
v.target_idx = len(v.freq_bins) - 1 # Index of the target frequency bin (0 or max)
v.cue_freq = v.freq_bins[v.target_idx]
v.correct_trials = 0
v.total_trials = 0
# --------------------------------

v.reward_count = 0 # Keep track of total rewards delivered
v.change_state = True
v.IT_mode = "baseline"        # "fixed" or "baseline"

v.lick_assist = True # give rewards if animal is not engaged
v.lick = 0 # did animal lick during reward
v.no_lick = 2 # dispense lick if not engaged
v.num_lick = 2

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(10)
    utime.sleep_ms(20)
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    hw.speaker.off()
    set_timer('session_timer', v.session_duration, True)
    print('{}, Task Started.'.format(get_current_time()))
    print('{}, before_camera_trigger'.format(get_current_time()))
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    hw.cameraTrigger.start()

def run_end():
    hw.reward.stop()
    hw.speaker.off()
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
      - Plays target frequency as a cue for v.cue_duration, sends 1 to BCI. Cue sound is uninterruptible.
      - After cue, sends 2 to BCI, turns off cue sound.
      - Monitors BCI control for target index. Speaker updates from BCI are active only after cue.
      - Times out to intertrial if target not reached within v.trial_duration.
    """
    if event == 'entry':
        
        if v.change_state:
            v.total_trials += 1
            hw.bci_link.send_int(1) 
            v.change_state = False 
            hw.speaker.sine(v.cue_freq) # Play target frequency cue
            v.cue_active = True # Set cue active flag
            set_timer('cue_end', v.cue_duration)

            print("{}, Trial #{} Start. Target Index: {}, Playing Cue Freq: {}".format(
                get_current_time(), v.total_trials, v.target_idx, v.cue_freq))
            print("{}, Sending 1 to BCI (Cue Start). Cue is active.".format(get_current_time()))

            timed_goto_state('intertrial', v.trial_duration)

    elif event == 'cue_end':
        v.cue_active = False # Clear cue active flag
        hw.speaker.off() # Stop cue sound. BCI cursor_update will now control the speaker.
        hw.bci_link.send_int(2) # Send 2 to BCI to indicate cue end
        print("{}, Cue ended. Sending 2 to BCI. Cue is now inactive. Waiting for cursor update.".format(get_current_time()))

    elif event == 'cursor_update':
        freq = hw.bci_link.spk 
        if freq is None:
            freq = v.freq_bins[len(v.freq_bins) // 2] 
        
        if not v.cue_active: # Only update speaker if cue is not active
            hw.speaker.sine(freq) 

            if freq >= v.target_freq:
                print("{}, Target Index Reached via BCI: {}".format(get_current_time(), freq))
                goto_state('threshold_crossed')

def threshold_crossed(event):
    if event == 'entry':
        # If cursor was updated during hold, speaker might be on. Ensure it's off or controlled as desired.
        # For now, assuming speaker state from trial's cursor_update is acceptable or handled by BCI not sending during hold.
        print("{}, Target Reached ({}), Entering Hold ({:.1f}ms)".format(
            get_current_time(), v.trial_type, v.hold_duration))
        timed_goto_state('reward', v.hold_duration)

    elif event == 'cursor_update':
        # If BCI updates during hold, it resets.
        # Speaker will also update here if not v.cue_active (which it won't be).
        freq = hw.bci_link.spk
        if freq is None: 
            freq = v.freq_bins[len(v.freq_bins) // 2]
        #else:  
        hw.speaker.sine(freq) # Speaker reflects BCI during failed hold attempt

        if freq < v.target_freq:
            print("{}, Cursor decreased below target, Resetting to Trial".format(get_current_time()))
            goto_state('trial')

def reward(event):
    if event == 'entry':
        print("{}, Entering Reward Window (Waiting for Lick, Timeout: {:.1f}s)".format(
            get_current_time(), v.reward_timer_duration / second))
        timed_goto_state('intertrial', v.reward_timer_duration)

        if v.lick_assist:
            if v.lick == 0:
                v.no_lick += 1
                if v.no_lick >= v.num_lick:
                    hw.reward.release()
                    v.no_lick = 0
            v.lick = 0

    elif event == 'lick':
        hw.reward.release()
        v.reward_count += 1
        v.correct_trials += 1
        v.lick = 1
        print("{}, Lick Detected! Reward #{} Delivered. Correct Trials: {}/{}. Advancing block.".format(
              get_current_time(), v.reward_count, v.correct_trials, v.total_trials))
        timed_goto_state('intertrial', v.stimulus_duration)

def intertrial(event):
    if event == 'entry':
        hw.bci_link.send_int(0)
        v.change_state = True 
        hw.speaker.off()

        print("{}, Entering Intertrial State (Duration: {:.1f}s)".format(
            get_current_time(), v.IT_duration / second))
        
        if v.IT_mode == "fixed":
            timed_goto_state('trial', v.IT_duration)
        else:
            set_timer('it_end', v.IT_duration)
            v.it_active = True

    elif event == 'it_end':
        v.it_active = False

    elif event == 'cursor_update':
        if v.IT_mode == "baseline":
            # Speaker should remain off during ITI baseline checking unless specified.
            # hw.speaker.off() # Explicitly ensure speaker is off
            freq = hw.bci_link.spk
            if freq is None:
                freq = v.freq_bins[len(v.freq_bins) // 2]
            if not v.it_active and not v.baseline_hold_active:
                if v.baseline_freq_range[0] <= freq <= v.baseline_freq_range[1]:
                    print("{}, Baseline frequency detected, returning to trial".format(get_current_time()))
                    set_timer('baseline_hold', v.baseline_hold)
                    v.baseline_hold_active = True
                
            elif v.baseline_hold_active and freq > v.baseline_freq_range[1]:
                disarm_timer('baseline_hold')
                v.baseline_hold_active = False
                print("{}, Cursor above baseline frequency".format(get_current_time()))
        else:
            print("{}, Cursor update during intertrial, no action taken.".format(get_current_time()))

    elif event == 'baseline_hold':
        print("{}, Baseline hold complete, transitioning to trial.".format(get_current_time()))
        v.baseline_hold_active = False
        goto_state('trial')

# -------------------------------------------------------------------------
# Event-handling functions
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'session_timer':
        print('{}, Session Timer Expired'.format(get_current_time()))
        stop_framework()
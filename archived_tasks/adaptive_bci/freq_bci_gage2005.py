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
    'it_end',       # Event triggered when the initial cue presentation ends
    'baseline_hold'
]

initial_state = 'intertrial' # Start in intertrial to shuffle first block

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
v.session_duration = 45 * minute
v.reward_duration = 60 * ms
v.hold_duration = 10 * ms  # Hold period at target index before reward state
v.baseline_hold = 500 * ms # Hold period of baseline period
v.trial_duration = 10 * second  # Maximum trial duration if target not reached
v.IT_duration = 4 * second  # Intertrial interval duration
v.reward_timer_duration = 2 * second # Max duration in reward state waiting for lick
v.stimulus_duration = 0.25 * second # Duration of stimulus presentation after rewarded lick
v.it_active = False # Flag to indicate if the IT period is active during baseline mode
v.baseline_hold_active = False
v.hold_required = False # does the animal need to hold in baseline period or not

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

# v.lick_assist = True # give rewards if animal is not engaged
# v.lick = 0 # did animal lick during reward
# v.no_lick = 2 # dispense lick if not engaged
# v.num_lick = 2

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
    print('task_started')
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
    print('session_ended')
    print('{}/{}, correct_trials'.format(v.correct_trials, v.total_trials))
    print('{}, total_rewards'.format(v.reward_count))

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
        freq = v.baseline_freq_range[-1]
        if v.change_state:
            v.total_trials += 1
            hw.bci_link.send_int(2) 
            v.change_state = False 
            hw.speaker.sine(freq)
            print('sending_2_to_BCI')
            print("{}, trial_start".format(v.total_trials))
            print("{}, target_index".format(v.target_idx))

            timed_goto_state('intertrial', v.trial_duration)

    elif event == 'cursor_update':
        freq = hw.bci_link.spk 
        if freq is None:
            freq = v.freq_bins[len(v.freq_bins) // 2] 
        print("{}, cursor_update_freq".format(freq))
        hw.speaker.sine(freq) 

        if freq >= v.target_freq:
            goto_state('threshold_crossed')

def threshold_crossed(event):
    if event == 'entry':
        # If cursor was updated during hold, speaker might be on. Ensure it's off or controlled as desired.
        # For now, assuming speaker state from trial's cursor_update is acceptable or handled by BCI not sending during hold.
        print("threshold_crossed")
        timed_goto_state('reward', v.hold_duration)

    elif event == 'cursor_update':
        # If BCI updates during hold, it resets.
        freq = hw.bci_link.spk
        if freq is None: 
            freq = v.freq_bins[len(v.freq_bins) // 2]
        #else:  
        hw.speaker.sine(freq) # Speaker reflects BCI during failed hold attempt

        if freq < v.target_freq:
            print("cursor_below_treshold")
            goto_state('trial')

def reward(event):
    if event == 'entry':
        v.reward_count += 1
        hw.reward.release()
        print("{}, reward_number".format(v.reward_count))
        timed_goto_state('intertrial', v.reward_timer_duration)

        hw.bci_link.send_int(3) # entering rewarded state

        # if v.lick_assist:
        #     if v.lick == 0:
        #         v.no_lick += 1
        #         if v.no_lick >= v.num_lick:
        #             hw.reward.release()
        #             v.no_lick = 0
        #     v.lick = 0

    elif event == 'lick':
        
        v.correct_trials += 1
        # v.lick = 1
        timed_goto_state('intertrial', v.stimulus_duration)

def intertrial(event):
    if event == 'entry':
        hw.bci_link.send_int(0)
        v.change_state = True 
        hw.speaker.off()

        print("{}, intertrial_start".format(v.IT_duration))
        
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
                    hw.bci_link.send_int(1) 
                    print("baseline_reached")
                    set_timer('baseline_hold', v.baseline_hold)
                    v.baseline_hold_active = True
                
            elif v.baseline_hold_active and freq > v.baseline_freq_range[1]:

                if v.hold_required:
                    disarm_timer('baseline_hold')
                    v.baseline_hold_active = False
                    print("cursor_above_baseline")
                    # If v.hold_required is False, the timer will continue even if freq > baseline_freq_range[1]
        else:
            print("intertrial_cursor_update")

    elif event == 'baseline_hold':
        v.baseline_hold_active = False
        goto_state('trial')

# -------------------------------------------------------------------------
# Event-handling functions
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'session_timer':
        print('session_timer_expired')
        stop_framework()
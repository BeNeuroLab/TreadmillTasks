from pyControl.utility import *
import hardware_definition as hw
from devices import *
import random

# -------------------------------------------------------------------------
 
# States
states = ['intertrial', 'stimulus_on', 'reward', 'punish_timeout', 'timeout'] # Added 'timeout' back
 
# Events
events = ['session_timer', 'lick', 'stimulus_timer', 'motion', 
          'punish_timeout_timer', 'timeout_timer'] # Added 'timeout_timer' back
 
# Initial state
initial_state = 'intertrial'

# -------------------------------------------------------------------------
 
# Variables
v.session_duration = 45 * minute
v.stimulus_duration = 2 * second
v.reward_duration = 60 * ms 
v.reward_period_duration = 2 * second
v.iti_duration = 2 * second  # Inter-trial interval

# Frequencies: First is GO, Second is NO-GO
v.spk_freqs = [2181, 12336] 
v.trial_types = [0,1]
v.go_stim_freq = v.spk_freqs[1] # Explicitly define Go frequency
v.nogo_stim_freq = v.spk_freqs[0] # Explicitly define No-Go frequency

# Punishment Timeout (for licking No-Go stimulus)
v.punish_timeout_duration = 2 * second # Duration animal must withhold licking during punishment timeout
v.punishment_on = False # if false, no punishment
v.reward_only = False # if true, only present rewarded stimulus

# Inactivity Timeout (Original Timeout)
v.target_duration = 40 * second  # Time without licking to trigger inactivity timeout
v.timeout_duration = 15 * second # Duration of the inactivity timeout pause

# --- Trial Counters ---
# Correct trials
v.correct_go_trials = 0   # Correct lick to Go stimulus
v.correct_nogo_trials = 0 # Correct withhold during No-Go stimulus
# Total trials
v.total_go_trials = 0     # Number of Go stimuli presented
v.total_nogo_trials = 0   # Number of No-Go stimuli presented

v.trial_in_block = 2  # Track position within the block

v.current_stim_freq = 0 # Variable to store the frequency of the current trial

# --- parameters you can adjust ---
v.block_size        = 20          # number of trials in a block
v.go_fraction       = 0.70        # overall Go probability
v.max_run_length    = 3           # cap on identical trials in a row
# ---------------------------------

def max_run_length(seq):
    """Return length of the longest stretch of identical values in seq."""
    if not seq:
        return 0
    run_len   = 1
    max_len   = 1
    last_item = seq[0]
    for item in seq[1:]:
        if item == last_item:
            run_len += 1
            if run_len > max_len:
                max_len = run_len
        else:
            run_len   = 1
            last_item = item
    return max_len


def make_block():
    """Create a pseudorandom mini-block that respects v.max_run_length."""
    n_go   = int(v.block_size * v.go_fraction)
    trials = [1] * n_go + [0] * (v.block_size - n_go)   # 1 = Go, 0 = No-Go

    # shuffle until the longest identical run is within the limit
    while True:
        random.shuffle(trials)          # or use pyControl's shuffle_list(trials)
        if max_run_length(trials) <= v.max_run_length:
            break

    v.trial_list = trials
    v.trial_i    = 0



# -------------------------------------------------------------------------

def shuffle_list(lst): # Fisher-Yates Shuffle
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i]  # Swap elements


# -------------------------------------------------------------------------
 
def run_start():
    # Initialise hardware
    hw.reward.reward_duration = v.reward_duration
    hw.speaker.set_volume(10) 
    hw.motionSensor.record() 
    hw.motionSensor.threshold = 10 
    # Set timers
    set_timer('session_timer', v.session_duration, True)
    set_timer('timeout_timer', v.target_duration) # Initialize the inactivity timer
    print('{}, Session Started'.format(get_current_time()))
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI)) 
    hw.cameraTrigger.start() 
    # call once at start-up
    make_block()
 
def run_end():
    # Turn off hardware components.
    hw.speaker.off()
    hw.reward.stop() 
    hw.motionSensor.off() 
    hw.motionSensor.stop() 
    hw.cameraTrigger.stop() 
    # Log session results
    print('Session Ended')
    total_trials_overall = v.total_go_trials + v.total_nogo_trials # Calculate total trials overall
    # Go Trial Summary
    go_perc = (v.correct_go_trials / v.total_go_trials * 100)
    print('Go Trials: Correct {}/{} ({:.2f}%)'.format(v.correct_go_trials, v.total_go_trials, go_perc))
    # No-Go Trial Summary
    nogo_perc = (v.correct_nogo_trials / v.total_nogo_trials * 100)
    print('NoGo Trials: Correct {}/{} ({:.2f}%)'.format(v.correct_nogo_trials, v.total_nogo_trials, nogo_perc)) 
    # Overall Summary
    total_correct_overall = v.correct_go_trials + v.correct_nogo_trials
    overall_perc = (total_correct_overall / total_trials_overall * 100)
    print('Overall: Correct {}/{} ({:.2f}%)'.format(total_correct_overall, total_trials_overall, overall_perc))
 
def intertrial(event):
    # Idle state between trials.
    if event == 'entry':
        hw.speaker.off() 
        timed_goto_state('stimulus_on', v.iti_duration)
        if v.trial_in_block >= 2:  # End of block, reset and shuffle
            v.trial_in_block = 0
            shuffle_list(v.trial_types)  # Shuffle order of next block
    elif event == 'lick':
        # Reset inactivity timer on any lick during ITI
        reset_timer('timeout_timer', v.target_duration) 
    elif event == 'timeout_timer':
        # Inactivity timer expired, go to the inactivity timeout state
        goto_state('timeout')
        
def stimulus_on(event):
    # Presents the auditory stimulus (Go or No-Go).
    if event == 'entry':
        # v.current_stim_freq = choice(v.spk_freqs)
        # ---- choose Go (1) or No-Go (0) from the pseudorandom list ----
        trial_type = v.trial_list[v.trial_i]
        v.trial_i += 1
        if v.trial_i >= len(v.trial_list):    # reached end of block?  build the next one
            make_block()

        v.current_stim_freq = v.go_stim_freq if trial_type else v.nogo_stim_freq

        if v.reward_only:                     # keep your existing “reward-only” override
            v.current_stim_freq = v.go_stim_freq
        # ----------------------------------------------------------------

        hw.speaker.sine(v.current_stim_freq) 
        print('{}, frequency'.format(v.current_stim_freq))
        set_timer('stimulus_timer', v.stimulus_duration)
        if v.current_stim_freq == v.go_stim_freq:
            v.total_go_trials += 1
        else:
            v.total_nogo_trials += 1
        
    elif event == 'lick':
        reset_timer('timeout_timer', v.target_duration) 
        if v.current_stim_freq == v.go_stim_freq:
            goto_state('reward')
        elif v.current_stim_freq == v.nogo_stim_freq:
            goto_state('punish_timeout')
            
    elif event == 'stimulus_timer':
        # Stimulus duration ended without a lick.
        hw.speaker.off() 
        if v.current_stim_freq == v.go_stim_freq:
            goto_state('intertrial') 
        elif v.current_stim_freq == v.nogo_stim_freq:
            v.correct_nogo_trials += 1
            print('Correct nogo trials: {}/{}'.format(v.correct_nogo_trials, v.total_nogo_trials))
            goto_state('intertrial') 
            
    elif event == 'timeout_timer':
         # Inactivity timer expired during stimulus presentation
        goto_state('timeout') # Go to inactivity timeout
        

def reward(event):
    # Delivers reward for correct Go response.
    if event == 'entry':
        hw.reward.release() 
        v.correct_go_trials += 1
        print('reward number {}/{}'.format(v.correct_go_trials, v.total_go_trials))
        reset_timer('timeout_timer', v.target_duration) 
        timed_goto_state('intertrial', v.reward_period_duration) 

def punish_timeout(event):
    # Timeout state entered after incorrect lick to No-Go stimulus.
    # Animal must refrain from licking for the specified duration.
    if event == 'entry':
        print('Punishment Timeout Started ({}s)'.format(v.punish_timeout_duration/second))
        set_timer('punish_timeout_timer', v.punish_timeout_duration)
        
    elif event == 'stimulus_timer':
        hw.speaker.off() 
        if v.punishment_on == False:
            reset_timer('punish_timeout_timer', v.iti_duration)


    elif event == 'lick':
        print('Lick during punishment timeout - Resetting timer')
        # Reset *both* timers on lick during punishment
        if v.punishment_on:
            reset_timer('punish_timeout_timer', v.punish_timeout_duration)
        reset_timer('timeout_timer', v.target_duration) 
        
    elif event == 'punish_timeout_timer':
        # Punishment timeout completed successfully.
        # Reset inactivity timer as we transition out successfully
        reset_timer('timeout_timer', v.target_duration) 
        goto_state('stimulus_on')
        
    elif event == 'exit':
        # Ensure punish timer is disarmed if exiting for other reasons (like inactivity timeout or session end)
        disarm_timer('punish_timeout_timer')

def timeout(event):
    "Inactivity timeout state"
    if event == 'entry':
        hw.speaker.off()
        timed_goto_state('intertrial', v.timeout_duration)
    elif event == 'exit':
        reset_timer('timeout_timer', v.target_duration)

def all_states(event):
    if event == 'session_timer':
        stop_framework()
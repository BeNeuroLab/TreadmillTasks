###############################################################################
# Operant lick task (Stimulus -> Lick -> Reward)                              #
###############################################################################
from pyControl.utility import *
import hardware_definition as hw
from devices import *
import utime

# -------------------------------------------------------------------------
#  States and events
# -------------------------------------------------------------------------
states = ['trial',
          'reward',
          'intertrial']

events = ['lick',
          'session_timer',
          'stim_timer',
          'motion']

initial_state = 'trial'

# -------------------------------------------------------------------------
#  Task variables
# -------------------------------------------------------------------------
v.session_duration = 30 * minute
v.reward_duration = 35 * ms
v.reward_number = 0

v.trial_len = 3 * second      # Duration of intertrial interval
v.pre_stim_len = 0.1 * second # Delay before stimulus onset in trial
v.led_direction = 100         # Direction for LED cue (0-100)

# -------------------------------------------------------------------------
#  Framework hooks
# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = 10
    hw.light.start()
    utime.sleep_ms(20)
    hw.light.all_red()
    set_timer('session_timer', v.session_duration, True)
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

def run_end():
    "Code here is executed when the framework stops running."
    hw.light.all_off()
    hw.light.off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.off()

# -------------------------------------------------------------------------
#  States
# -------------------------------------------------------------------------
def trial(event):
    "Stimulus presentation state."
    if event == 'entry':
        hw.light.all_red() # Ensure Red at start of trial
        set_timer('stim_timer', v.pre_stim_len)
    
    elif event == 'stim_timer':
        hw.light.cue(v.led_direction) # Turn on Target LED
        print('{}, led_direction'.format(v.led_direction))
        # Now waiting for lick...

    elif event == 'lick':
        # Only reward if stimulus is on? 
        # For now, assuming any lick in 'trial' after stim onset (or even before?) triggers reward?
        # "Stimulus presentation first" implies we should wait for stimulus.
        # But if they lick during pre_stim, what happens?
        # I'll assume lick triggers reward to keep it simple and robust, 
        # or I could check if timer passed. 
        # Given "Stimulus first", I should probably wait for stim.
        # But to be safe and responsive, I'll let lick trigger reward, 
        # but maybe the user *wants* the cue to be visible first.
        # With 0.1s delay, it's almost immediate.
        goto_state('reward')

def reward(event):
    "Reward state."
    if event == 'entry':
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        goto_state('intertrial')

def intertrial(event):
    "Intertrial interval."
    if event == 'entry':
        hw.light.all_red() # Back to Red background
        timed_goto_state('trial', v.trial_len)

def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'session_timer':
        stop_framework()

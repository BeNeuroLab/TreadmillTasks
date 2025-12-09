# Task: Run target distance -> Wait for stop -> Stimulus (LED+Sound) -> Lick -> Reward

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import utime

# -------------------------------------------------------------------------
#  States and events
# -------------------------------------------------------------------------
states = ['trial',
          'wait_for_stop',
          'stim_on',
          'reward',
          'intertrial']

events = ['lick',
          'session_timer',
          'motion',
          'stop_timer',
          'wait_to_stop_timer',
          'response_timer']

initial_state = 'trial'

# -------------------------------------------------------------------------
#  Task variables
# -------------------------------------------------------------------------
v.session_duration = 30 * minute
v.reward_duration = 35 * ms
v.reward_number = 0

v.target_distance = 20       # Arbitrary distance units (e.g. clicks)
v.current_distance = 0
v.motion_threshold = 2        # How much distance per motion event

v.stop_duration = 0.5 * second      # Duration mouse must be still to trigger stim
v.wait_to_stop_time = 5 * second    # Max time to wait for stop before aborting
v.response_window = 2 * second      # Time to lick after stim onset
v.intertrial_duration = 2 * second  # ITI

v.led_direction = 100         # Direction for LED cue
v.go_stim_freq = 10000        # Frequency for Go tone

v.last_motion_time = 0

# -------------------------------------------------------------------------
#  Framework hooks
# -------------------------------------------------------------------------
def run_start():
    "Code here is executed when the framework starts running."
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_threshold
    hw.light.start()
    hw.speaker.set_volume(10) # Ensure speaker volume is set
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
    hw.speaker.off()
    hw.reward.stop()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.off()

# -------------------------------------------------------------------------
#  States
# -------------------------------------------------------------------------
def trial(event):
    "Run state: Measure distance."
    if event == 'entry':
        hw.light.all_red()
        v.current_distance = 0
        print('{}, trial_start'.format(get_current_time()))
    
    elif event == 'motion':
        v.current_distance += v.motion_threshold
        # print('{}, distance'.format(v.current_distance)) # Optional: print distance
        
        if v.current_distance >= v.target_distance:
            goto_state('wait_for_stop')

def wait_for_stop(event):
    "Wait for mouse to stop for v.stop_duration."
    if event == 'entry':
        print('{}, enter_wait_for_stop'.format(get_current_time()))
        v.last_motion_time = get_current_time()
        set_timer('wait_to_stop_timer', v.wait_to_stop_time)
        # Start checking for stop immediately
        set_timer('stop_timer', v.stop_duration) 

    elif event == 'motion':
        v.last_motion_time = get_current_time()
        # Reset stop timer because moved
        set_timer('stop_timer', v.stop_duration) 
        
    elif event == 'stop_timer':
        # If we are here, it means no motion occurred for v.stop_duration
        # Double check just in case (though timer reset should handle it)
        if (get_current_time() - v.last_motion_time) >= v.stop_duration:
            goto_state('stim_on')
            
    elif event == 'wait_to_stop_timer':
        # Timed out waiting for stop
        print('{}, wait_for_stop_timeout'.format(get_current_time()))
        goto_state('intertrial')

def stim_on(event):
    "Stimulus presentation state."
    if event == 'entry':
        print('{}, stimulus_on'.format(get_current_time()))
        hw.light.cue(v.led_direction)
        hw.speaker.sine(v.go_stim_freq)
        set_timer('response_timer', v.response_window)
        
    elif event == 'lick':
        goto_state('reward')
        
    elif event == 'response_timer':
        print('{}, miss'.format(get_current_time()))
        goto_state('intertrial')

def reward(event):
    "Reward state."
    if event == 'entry':
        hw.speaker.off()
        hw.light.all_red()
        hw.reward.release()
        v.reward_number += 1
        print('{}, reward_number'.format(v.reward_number))
        timed_goto_state('intertrial', 0.5 * second) # Short delay before ITI

def intertrial(event):
    "Intertrial interval."
    if event == 'entry':
        hw.speaker.off()
        hw.light.all_red()
        print('{}, intertrial_start'.format(get_current_time()))
        timed_goto_state('trial', v.intertrial_duration)

def all_states(event):
    """
    Executes before the state code.
    """
    if event == 'session_timer':
        stop_framework()

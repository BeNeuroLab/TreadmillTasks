# Importing required libraries
from pyControl.utility import *
import hardware_definition as hw
from devices import *
from random import randint
import time  # Import the time library

# States and events
states = ['session_start', 'session_middle', 'session_end', 'trial_start', 'trial_on', 'trial_off']
events = ['session_timer', 'sol_timer', 'motion', 'trial_end', 'activate_sol', 'delay_goto', 'quiet_period_end','quiet_period_start']

initial_state = 'session_start'

# Variables
v.session_duration = 20 * minute
v.quiet_period = 1 * minute
v.trial_number = 0
v.stim_dir = None
v.max_gap_duration = 6 * second
v.max_IT_duration = 3 * second
v.max_led_duration = 100 * ms
v.min_motion = 15  # cm - minimum distance to trigger an event

# State-independent Code
def cue_random_sol(SolDevice: shakeStim):
    stim_dir = randint(0, SolDevice.n_directions-1)
    SolDevice.all_off()
    SolDevice.cue_sol(stim_dir)
    print('{}, Sol_direction'.format(stim_dir))
    return stim_dir

# Define behaviour
def run_start():
    set_timer('session_timer', v.session_duration + 2 * v.quiet_period, True)
    set_timer('quiet_period_end', v.quiet_period, True)
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.min_motion
    hw.cameraTrigger.start()
    hw.earthquake_stim.all_off()
    print('CPI={}'.format(hw.motionSensor.sensor_x.CPI))

def run_end():
    hw.earthquake_stim.all_off()
    hw.motionSensor.off()
    hw.off()

def session_start(event):
    if event == 'quiet_period_end':
        goto_state('session_middle')

def session_middle(event):
    if event == 'entry':
        set_timer('quiet_period_start', v.session_duration, True)
        set_timer('delay_goto', 1)  # Set a 1ms delay to transition to 'trial_start'
    elif event == 'delay_goto':
        goto_state('trial_start')  # Now this should be a valid state transition


def session_end(event):
    if event == 'entry':
        pass

def trial_start(event):
    if event == 'entry':
        v.stim_dir = None
        set_timer('activate_sol', randint(1, 10) * second)
        set_timer('delay_goto', 1)
    elif event == 'delay_goto':
        goto_state('trial_on')

def trial_on(event):
    if event == 'activate_sol':
        timestamp = time.time()
        cue_random_sol(hw.earthquake_stim)
        set_timer('sol_timer', v.max_led_duration, False)
    elif event == 'sol_timer':
        hw.earthquake_stim.all_off()
        goto_state('trial_off')

def trial_off(event):
    if event == 'entry':
        set_timer('trial_end', randint(v.max_led_duration, v.max_IT_duration))
    elif event == 'trial_end':
        goto_state('trial_start')

# State-independent behaviour
def all_states(event):
    if event == 'quiet_period_start':
        goto_state('session_end')
    elif event == 'session_timer':
        hw.motionSensor.stop()
        stop_framework()

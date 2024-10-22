# Importing required libraries
from pyControl.utility import *
import hardware_definition as hw
from devices import *
from random import randint
import time  # Import the time library

#port_exp=Port_expander(port=hw.board.port_8)
earthquake_stim = shakeStim(port_exp=Port_expander(port=hw.board.port_8))


'''
# Need to define the earthquake here to avoid initializing the pow pins in hardware definition
earthquake_stim = shakeStim(port_exp=Port_expander(port=hw.board.port_8))


# States and events
'''
states = [
    'intertrial',
    'trial',
]
events = [
    'IT_timer',
    'trial_timer',
    'session_timer',
    'motion'
]

initial_state = "trial"
'''

initial_state = 'intertrial'

# Variables
v.min_motion = 15
v.sol_number = 0
v.sol_duration = 100 * ms
v.IT_duration = 1 * second
v.trial_duration = 1 * second
v.session_duration = 10 * minute

# Run behaviour
def run_start():
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.min_motion
    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration, True)
    earthquake_stim.all_off()
    print('CPI={}'.format(hw.motionSensor.sensor_x.CPI))

def run_end():
    earthquake_stim.all_off()
    hw.motionSensor.off()
    hw.off()

# States and transitions
def intertrial(event):

    if event == 'entry':
        earthquake_stim.all_off()
        set_timer('IT_timer', v.IT_duration, True)

    elif event == 'IT_timer':
        if v.sol_number < 6:
            goto_state('trial')
        elif v.sol_number == 6:
            v.sol_number = 0
            goto_state('trial')


    elif event == 'session_timer':
        hw.motionSensor.stop()
        stop_framework()

            
    
'''

def trial(event):
    earthquake_stim.sol_1.off()
    # if event == 'entry':
    #     set_timer('trial_timer', v.trial_duration, True)

    # elif event == 'trial_timer':
    #     earthquake_stim.cue_sol(0)  # Activate solenoid
    #     print('{}, Sol_direction'.format(v.sol_number))
    #     # v.sol_number = v.sol_number + 1
    #     print('Next solenoid {}'.format(v.sol_number))
    #     timed_goto_state('intertrial', v.sol_duration)

    # elif event == 'session_timer':
    #     hw.motionSensor.stop()
    #     stop_framework()

    







        



    




    

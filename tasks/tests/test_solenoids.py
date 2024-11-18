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
    'intertrial_timer',
    'trial_timer',
    'session_timer',
    'motion'
]

initial_state = "trial"

# Variables
v.min_motion = 15
v.sol_duration = 1 * second
v.sol_number = 0
v.intertrial_duration = 1 * second
v.trial_duration = 2 * second
v.session_duration = 10 * minute
v.max_solenoids = 11



def run_start():
    earthquake_stim.kill_switch.on()

def run_end():
    earthquake_stim.kill_switch.off()



# States and transitions
def intertrial(event):

    if event == 'entry':
        earthquake_stim.sol_off(v.sol_number)
        v.sol_number = v.sol_number + 1
        set_timer('intertrial_timer', v.intertrial_duration, True)
        

    elif event == 'intertrial_timer':
        goto_state('trial')




def trial(event):

    if event == 'entry':
        if v.sol_number == v.max_solenoids:
            stop_framework()
        set_timer('trial_timer', v.trial_duration, True)


    if event == 'trial_timer':
        print('{}, Sol_number'.format(v.sol_number))
        earthquake_stim.sol_on(v.sol_number)
        timed_goto_state('intertrial', v.sol_duration)

    # if event == 'entry':
    #     set_timer('trial_timer', v.trial_duration, True)

    # elif event == 'trial_timer':
    #     earthquake_stim.cue_sol(0)  # Activate solenoid
    #     print('{}, Sol_direction'.format(v.sol_number))
    #     # 
    #     print('Next solenoid {}'.format(v.sol_number))
    #     timed_goto_state('intertrial', v.sol_duration)

    # elif event == 'session_timer':
    #     hw.motionSensor.stop()
    #     stop_framework()

    







        



    




    

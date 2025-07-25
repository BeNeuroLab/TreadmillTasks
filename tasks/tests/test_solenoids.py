# Importing required libraries
from pyControl.utility import *
import hardware_definition as hw
from devices import *
from random import randint
import time  # Import the time library

#port_exp=Port_expander(port=hw.board.port_8)
#earthquake_stim = shakeStim(port_exp=Port_expander(port=hw.board.port_8))


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
v.sol_duration = 50 * ms
v.sol_number = 0
v.min_motion = 7
v.intertrial_duration = 1 * second
v.trial_duration = 1 * second
v.session_duration = 10 * minute
v.max_solenoids = 12



def run_start():
    """
    Code here is executed when the framework starts running.
    """
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.min_motion
    print('{}, CPI'.format(hw.motionSensor.sensor_x.CPI))

    set_timer('session_timer', v.session_duration, True)

    hw.earthquake_stim.kill_switch.on()

    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()


def run_end():
    """
    Code here is executed when the framework stops running
    """
    hw.motionSensor.stop()
    hw.earthquake_stim.kill_switch.off()
    hw.cameraTrigger.stop()
    hw.off()



# States and transitions
def intertrial(event):

    if event == 'entry':
        hw.earthquake_stim.sol_off(v.sol_number)
        v.sol_number = v.sol_number + 1
        set_timer('intertrial_timer', v.intertrial_duration, True)
        

    elif event == 'intertrial_timer':
        goto_state('trial')

def all_states(event):
    if event == 'session_timer':
        stop_framework()

def trial(event):

    if event == 'entry':
        if v.sol_number == v.max_solenoids:
            v.sol_number = 0
        set_timer('trial_timer', v.trial_duration, True)


    if event == 'trial_timer':
        print('{}, Sol_number'.format(v.sol_number))
        hw.earthquake_stim.sol_on(v.sol_number)
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

    







        



    




    

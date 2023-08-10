# PyTreadmillTask

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math

# -------------------------------------------------------------------------
# States and events.
# -------------------------------------------------------------------------

states = ['intertrial',
          'trial_start',
          'stim_on',
          'reward',
          'penalty']

events = ['motion',
          'lick',
          'lick_off',
          'session_timer',
          'IT_timer',
          'max_IT_timer',
          'stim_timer',
          'reward_timer',
          'audio_freq'
          ]

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables.
# -------------------------------------------------------------------------

# general parameters
v.target_angle___ = {0: 5 * math.pi / 6,
                     1: 2 * math.pi / 3,
                     2: math.pi / 2,
                     3: math.pi / 3,
                     4: math.pi / 6}

v.audio_f_range___ = (10000, 20000)  # between 10kHz and 20kHz, loosely based on Heffner & Heffner 2007

# session params
v.session_duration = 1 * hour
v.reward_duration = 30 * ms
v.penalty_duration = 10 * second
v.trial_number = 0
v.centre_led_p = 0.9  # probability of cueing the centre LED

# intertrial params
v.min_IT_movement = 10  # cm - must be a multiple of 5
v.min_IT_duration = 1 * second
v.max_IT_duration = 15 * second
v.IT_duration_done___ = False
v.IT_distance_done___ = False
v.x___ = 0
v.y___ = 0

# trial params
v.stim_len = 10 * second
v.distance_to_target = 20  # cm - must be a multiple of 5
v.target_angle_tolerance = math.pi / 12  # deg_rad
v.led_direction = -1
v.trial_start_len = 100 * ms

# -------------------------------------------------------------------------
# State-independent Code
# -------------------------------------------------------------------------


def cue_centre_led_p(LedDevice: LEDStim, p: float =0.9):
    """
    Cues the central led at the probablity `p`, else cues another led randomly
    """
    if withprob(p):
        stim_dir = 2
    else:
        cues = list(v.target_angle___.keys()).remove(2)
        stim_dir = choice(cues)
    LedDevice.all_off()
    LedDevice.cue_led(stim_dir)
    print('{}, LED_direction'.format(stim_dir))

    return stim_dir


def arrived_to_target(dX: float, dY: float,
                      stim_direction: int,
                      target_angle_tolerance: float):
    """
    checks the motion critereon
    MUST have 5 stim directions
    """
    assert stim_direction < 5, 'wrong direction value'

    move_angle = math.atan2(dY, dX)
    print('{}, run_angle'.format(move_angle)
    if abs(move_angle - v.target_angle___[stim_direction]) < target_angle_tolerance:
        return True
    else:
        return False


def audio_mapping(d_a: float) -> float:
    """
    freq = (-10kHz/300)d_a + 15kHz
    """
    return mean(v.audio_f_range___) - (v.audio_f_range___[0] * d_a / v.target_angle___[0] * 2)


def audio_feedback(speaker,
                   dX: float, dY: float,
                   stim_direction: int):
    """ Set the audio frequency based on the direction of the movement. """
    angle = math.atan2(dY, dX)
    audio_freq = audio_mapping(angle - v.target_angle___[stim_direction])
    speaker.sine(audio_freq)


# -------------------------------------------------------------------------
# Define behaviour.
# -------------------------------------------------------------------------


# Run start and stop behaviour.
def run_start():
    "Code here is executed when the framework starts running."
    set_timer('session_timer', v.session_duration, True)
    hw.motionSensor.record()
    hw.speaker.set_volume(90)
    hw.speaker.off()
    hw.LED_Delivery.all_off()
    print('CPI={}'.format(hw.motionSensor.sensor_x.CPI))


def run_end():
    """ 
    Code here is executed when the framework stops running.
    Turn off all hardware outputs.
    """
    hw.LED_Delivery.all_off()
    hw.rewardSol.off()
    hw.speaker.off()
    hw.motionSensor.off()
    hw.off()

# State behaviour functions.
def intertrial(event):
    "intertrial state behaviour"
    if event == 'entry':
        # coded so that at this point, there is clean air coming from every direction
        set_timer('IT_timer', v.min_IT_duration)
        set_timer('max_IT_timer', v.max_IT_duration)
        hw.LED_Delivery.all_off()
        v.IT_duration_done___ = False
        v.IT_distance_done___ = False
        hw.motionSensor.threshold = v.min_IT_movement # to issue an event only after enough movement
    elif event == 'exit':
        disarm_timer('IT_timer')
    elif event == 'IT_timer':
        v.IT_duration_done___ = True
        if v.IT_distance_done___:
            goto_state('trial_start')
    elif event == 'motion':
        v.IT_distance_done___ = True
        if v.IT_duration_done___:
            goto_state('trial_start')
    elif event == 'max_IT_timer':
        hw.LED_Delivery.all_on()


def trial_start(event):
    "beginning of the trial"
    if event == 'entry':
        v.trial_number += 1
        print('{}, trial_number'.format(v.trial_number))
        hw.LED_Delivery.all_off()
        timed_goto_state('stim_on', v.trial_start_len)


def stim_on(event):
    "stimulation onset"
    if event == 'entry':
        set_timer('stim_timer', v.stim_len)
        v.led_direction = cue_random_led(hw.LED_Delivery)
        hw.motionSensor.threshold = v.distance_to_target
    elif event == 'exit':
        disarm_timer('stim_timer')
        hw.speaker.off()
    elif event == 'motion':
        arrived = arrived_to_target(v.x___, v.y___,
                                    v.led_direction,
                                    v.target_angle_tolerance)

        audio_feedback(hw.speaker, v.x___, v.y___, v.led_direction)

        if arrived is True:
            goto_state('reward')
        elif arrived is False:
            goto_state('penalty')
    elif event == 'stim_timer':
        goto_state('penalty')


def reward(event):
    "reward state"
    if event == 'entry':
        hw.LED_Delivery.all_off()
        set_timer('reward_timer', v.reward_duration, False)
        hw.rewardSol.on()
        print('{}, reward_on'.format(get_current_time()))
    elif event == 'exit':
        disarm_timer('reward_timer')
    elif event == 'reward_timer':
        hw.rewardSol.off()
        goto_state('intertrial')


def penalty(event):
    "penalty state"
    if event == 'entry':
        hw.LED_Delivery.all_on()
        print('{}, penalty_on'.format(get_current_time()))
        timed_goto_state('intertrial', v.penalty_duration)


# State independent behaviour.
def all_states(event):
    """
    Code here will be executed when any event occurs,
    irrespective of the state the machine is in.
    """
    if event == 'motion':
        # read the motion registers
        # to convert to cm, divide by CPI and multiply by 2.54
        v.x___ = hw.motionSensor.x #/ hw.motionSensor.sensor_x.CPI * 2.54
        v.y___ = hw.motionSensor.y #/ hw.motionSensor.sensor_x.CPI * 2.54
        print('{},{}, dM'.format(v.x___, v.y___))
    elif event == 'lick':
        #TODO: handle the lick data better
        pass
    elif event == 'session_timer':
        hw.motionSensor.stop()
        stop_framework()

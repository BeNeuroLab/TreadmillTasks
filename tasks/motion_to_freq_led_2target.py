"""Two-target LED motion task (y-motion to center)

Behavior
- Each trial starts with either the left or right LED target lit.
- Mouse must move in the correct y-direction to bring the LED to the center.
- When the LED reaches the center, enter reward state; deliver water on lick.

Notes
- Uses the LED strip API from devices.LEDStim.LedStrip, matching usage in
  tasks/moce/*.py so the LEDs work reliably.
- Direction mapping can be flipped via `v.y_positive_is_right` if needed.
"""

from pyControl.utility import *
import hardware_definition as hw
from devices import *
import utime


# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'intertrial',
    'trial',
    'reward',
    'stopped'
]

events = [
    'session_timer',
    'motion',
    'lick',
    'trial_timer',
    'reward_timer',
    'motion_check_timer',
    'stop_button'
]

initial_state = 'intertrial'


# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session parameters
v.session_duration = 45 * minute

# Trial parameters
v.intertrial_duration = 3 * second   # Minimum time between trials
v.trial_timeout = 15 * second        # Max time to reach center
v.motion_wait_time = 1 * second      # Time without motion before trial can start
v.reward_duration = 40 * ms

# LED/target settings
v.center_target = 50                 # Center index for LED strip (1..100)
v.left_start = 1                     # Left-most LED index
v.right_start = 100                  # Right-most LED index
v.led_step_per_event = 2             # How much LED moves per qualifying motion event
v.y_positive_is_right = True         # Flip if y sign is reversed on your rig

# Motion sensor
v.motion_threshold = 10              # Motion event threshold
v.cpi = 100                          # Will be updated from sensor

# Tracking
v.reward_number = 0
v.last_motion_time = 0
v.motion_detected = False
v.intertrial_start_time = 0
v.start_side = 'left'                # 'left' or 'right' for current trial
v.current_led = v.center_target


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def reset_trial_vars():
    v.motion_detected = False
    v.current_led = v.center_target
    v.start_side = 'left'


def pick_start_side():
    if random() < 0.5:
        v.start_side = 'left'
        v.current_led = v.left_start
    else:
        v.start_side = 'right'
        v.current_led = v.right_start


def show_led(value:int):
    try:
        hw.light.cue(value)
        print('{}, led_number'.format(value))
    except Exception:
        pass


def move_towards_center(dy:int):
    """Update v.current_led toward center based on y-motion sign.

    - If starting on left: need rightward motion to increase LED value to 50.
    - If starting on right: need leftward motion to decrease LED value to 50.
    - Wrong direction is ignored (no movement of LED).
    """
    if dy == 0:
        return

    # Determine if dy moves in the correct direction toward center.
    if v.start_side == 'left':
        rightward = (dy > 0) if v.y_positive_is_right else (dy < 0)
        if rightward:
            v.current_led = min(v.center_target, v.current_led + v.led_step_per_event)
    else:  # start_side == 'right'
        leftward = (dy < 0) if v.y_positive_is_right else (dy > 0)
        if leftward:
            v.current_led = max(v.center_target, v.current_led - v.led_step_per_event)

    show_led(v.current_led)


# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_threshold

    # LED strip startup modeled after moce tasks
    hw.light.start()
    utime.sleep_ms(20)
    hw.light.all_red()
    hw.light.cue_bilateral(False)  # single-side target so we can start at left or right

    # CPI, camera, timers
    if hasattr(hw.motionSensor, 'sensor_x'):
        v.cpi = hw.motionSensor.sensor_x.CPI
    print('{}, CPI'.format(v.cpi))
    print('{}, motion_threshold'.format(v.motion_threshold))
    print('{}, motion_wait_time'.format(v.motion_wait_time))
    print('{}, trial_timeout'.format(v.trial_timeout))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration, True)


def run_end():
    try:
        hw.light.all_off()
        hw.light.off()
    except Exception:
        pass
    hw.motionSensor.stop()
    hw.motionSensor.off()
    hw.cameraTrigger.stop()
    hw.off()


# -------------------------------------------------------------------------
# State Machine
# -------------------------------------------------------------------------
def intertrial(event):
    if event == 'entry':
        reset_trial_vars()
        v.intertrial_start_time = get_current_time()
        set_timer('motion_check_timer', v.intertrial_duration, True)
        try:
            hw.light.all_red()
        except Exception:
            pass

    elif event == 'motion':
        v.motion_detected = True
        v.last_motion_time = get_current_time()

    elif event == 'motion_check_timer':
        time_in_intertrial = get_current_time() - v.intertrial_start_time
        if time_in_intertrial >= v.intertrial_duration:
            # Require a short stillness before starting next trial
            if not v.motion_detected:
                goto_state('trial')
            else:
                v.motion_detected = False
                set_timer('motion_check_timer', v.motion_wait_time, True)
        else:
            set_timer('motion_check_timer', v.motion_wait_time, True)

    elif event == 'stop_button':
        goto_state('stopped')


def trial(event):
    if event == 'entry':
        pick_start_side()
        show_led(v.current_led)
        set_timer('trial_timer', v.trial_timeout, True)

    elif event == 'exit':
        disarm_timer('trial_timer')

    elif event == 'motion':
        # Use y-motion sign to update LED position toward center
        dy = 0
        try:
            dy = hw.motionSensor.y
        except Exception:
            pass
        move_towards_center(dy)

        # Check if target reached
        if v.current_led == v.center_target:
            goto_state('reward')

    elif event == 'trial_timer':
        goto_state('intertrial')

    elif event == 'stop_button':
        goto_state('stopped')


def reward(event):
    if event == 'entry':
        set_timer('reward_timer', 5 * second, True)

    elif event == 'exit':
        disarm_timer('reward_timer')

    elif event == 'lick':
        v.reward_number += 1
        hw.reward.release()
        print('{}, reward_number'.format(v.reward_number))
        goto_state('intertrial')

    elif event == 'reward_timer':
        goto_state('intertrial')

    elif event == 'stop_button':
        goto_state('stopped')


def stopped(event):
    if event == 'entry':
        disarm_timer('motion_check_timer')
        disarm_timer('trial_timer')
        disarm_timer('reward_timer')
        try:
            hw.light.all_off()
        except Exception:
            pass

    elif event == 'stop_button':
        goto_state('intertrial')


# -------------------------------------------------------------------------
# All-states events
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'session_timer':
        print('Session Timer Expired')
        print('{}, total_rewards'.format(v.reward_number))
        stop_framework()


# ===== Timer-lite Two-target LED motion task (fewer timers, no 'stopped') =====
from pyControl.utility import *
import hardware_definition as hw
from devices import *
import utime
import math

# -------------------------------------------------------------------------
# States / Events (reduced)
# -------------------------------------------------------------------------
states = ['intertrial', 'trial', 'reward']
events  = [
    'session_timer',
    'motion',
    'lick',
    'quiescence_timer',
]
initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Parameters
# -------------------------------------------------------------------------
# Session
v.session_duration      = 45 * minute

# ITI / gating
v.intertrial_duration   = 3 * second     # minimum ITI
v.motion_wait_time      = 1 * second     # must be this long without motion

# Trial / reward
v.trial_timeout         = 15 * second    # max time to reach center
v.reward_window         = 5 * second     # lick window (uses timed_goto_state)
v.reward_duration       = 40 * ms

# LED / target
v.center_target         = 50             # 1..100
v.left_start            = 10
v.right_start           = 90
v.y_positive_is_right   = True

# Audio (log-spaced discrete steps)
v.start_freq_hz         = 2000
v.goal_freq_hz          = 12000
v.num_steps             = 3
v.current_step          = 0
v.current_freq          = v.start_freq_hz

# Motion sensor
v.motion_threshold      = 1
v.cpi                   = 100

# Tracking
v.reward_number         = 0
v.last_motion_time      = 0
v.intertrial_entry_time = 0
v.start_side            = 'left'  # 'left' or 'right'
v.current_led           = v.center_target
v.led_step_size         = 0.0

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def reset_trial_vars():
    v.current_step = 0
    v.current_freq = v.start_freq_hz
    v.current_led  = v.center_target
    v.start_side   = 'left'

def pick_start_side():
    # 50/50 side choice
    if random() < 0.5:
        v.start_side = 'left'
        v.current_led = v.left_start
        span = max(1, v.center_target - v.left_start)
    else:
        v.start_side = 'right'
        v.current_led = v.right_start
        span = max(1, v.right_start - v.center_target)
    # step size so that num_steps steps lands exactly on center
    v.led_step_size = span / v.num_steps

def show_led(value:int):
    try:
        hw.light.cue(value)
        print('{}, led_number'.format(value))
    except Exception:
        pass

def _led_for_step(step:int) -> int:
    step = max(0, min(v.num_steps, step))
    if v.start_side == 'left':
        pos = int(round(v.left_start + step * v.led_step_size))
        return min(v.center_target, max(v.left_start, pos))
    else:
        pos = int(round(v.right_start - step * v.led_step_size))
        return max(v.center_target, min(v.right_start, pos))

def _calculate_frequency_for_step(step:int) -> int:
    octaves = math.log2(v.goal_freq_hz / v.start_freq_hz)
    step_fraction = max(0, min(v.num_steps, step)) / v.num_steps
    mult = 2 ** (octaves * step_fraction)
    return int(v.start_freq_hz * mult)

def _update_audio_for_step(step:int) -> None:
    v.current_step = max(0, min(v.num_steps, step))
    v.current_freq = _calculate_frequency_for_step(v.current_step)
    hw.speaker.sine(v.current_freq)
    print('{}, step'.format(v.current_step))
    print('{}, frequency'.format(v.current_freq))
    if v.current_step >= v.num_steps:
        hw.speaker.sine(v.goal_freq_hz)
        print('{}, target_reached'.format(v.goal_freq_hz))

def move_towards_center(dy:int):
    """Advance one step toward center if dy is in the correct direction."""
    if dy == 0 or v.current_step >= v.num_steps:
        return
    advanced = False
    if v.start_side == 'left':
        rightward = (dy > 0) if v.y_positive_is_right else (dy < 0)
        if rightward:
            v.current_step += 1
            advanced = True
    else:
        leftward = (dy < 0) if v.y_positive_is_right else (dy > 0)
        if leftward:
            v.current_step += 1
            advanced = True
    if advanced:
        v.current_led = _led_for_step(v.current_step)
        show_led(v.current_led)
        _update_audio_for_step(v.current_step)

def arm_quiescence_check():
    """
    Single self-rearming ITI gate:
      Start trial when BOTH:
        (1) ITI >= v.intertrial_duration
        (2) No motion for >= v.motion_wait_time
    """
    now = get_current_time()
    need_iti   = max(0, v.intertrial_duration - (now - v.intertrial_entry_time))
    need_quiet = max(0, v.motion_wait_time     - (now - v.last_motion_time))
    if (need_iti == 0) and (need_quiet == 0):
        goto_state('trial')
    else:
        delay = max(need_iti, need_quiet, 100)  # >=100 ms to keep CPU load low
        set_timer('quiescence_timer', delay, True)

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.reward.reward_duration = v.reward_duration
    hw.speaker.set_volume(15)

    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_threshold

    # LED strip init (moce-style)
    hw.light.start()
    utime.sleep_ms(20)
    hw.light.all_red()
    hw.light.cue_bilateral(False)  # single-side targets

    if hasattr(hw.motionSensor, 'sensor_x'):
        v.cpi = hw.motionSensor.sensor_x.CPI
    print('{}, CPI'.format(v.cpi))
    print('{}, motion_threshold'.format(v.motion_threshold))
    print('{}, motion_wait_time'.format(v.motion_wait_time))
    print('{}, trial_timeout'.format(v.trial_timeout))
    print('{}, start_frequency'.format(v.start_freq_hz))
    print('{}, goal_frequency'.format(v.goal_freq_hz))
    print('{}, num_steps'.format(v.num_steps))
    print('{}, before_camera_trigger'.format(get_current_time()))
    hw.cameraTrigger.start()

    set_timer('session_timer', v.session_duration, True)

def run_end():
    try:
        hw.light.all_off()
        hw.light.off()
    except Exception:
        pass
    hw.speaker.off()
    hw.motionSensor.off()
    hw.motionSensor.stop()
    hw.cameraTrigger.stop()
    hw.off()

# -------------------------------------------------------------------------
# States
# -------------------------------------------------------------------------
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        reset_trial_vars()
        now = get_current_time()
        v.intertrial_entry_time = now
        v.last_motion_time      = now
        try:
            hw.light.all_red()
        except Exception:
            pass
        arm_quiescence_check()

    elif event == 'motion':
        v.last_motion_time = get_current_time()

    elif event == 'quiescence_timer':
        arm_quiescence_check()

    elif event == 'exit':
        disarm_timer('quiescence_timer')

def trial(event):
    if event == 'entry':
        pick_start_side()
        v.current_step = 0
        v.current_led  = _led_for_step(v.current_step)
        show_led(v.current_led)
        hw.speaker.sine(v.start_freq_hz)
        # Use timed_goto_state for timeout (no named trial_timer)
        timed_goto_state('intertrial', v.trial_timeout)

    elif event == 'motion':
        # Use y-motion sign to step toward center
        dy = 0
        try:
            dy = hw.motionSensor.y
        except Exception:
            pass
        move_towards_center(dy)

        if v.current_step >= v.num_steps:
            goto_state('reward')

    elif event == 'exit':
        hw.speaker.off()

def reward(event):
    if event == 'entry':
        # Use timed_goto_state for lick window (no named reward_timer)
        timed_goto_state('intertrial', v.reward_window)

    elif event == 'lick':
        v.reward_number += 1

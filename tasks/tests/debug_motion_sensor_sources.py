from pyControl.utility import *
import hardware_definition as hw
from devices import *


# -------------------------------------------------------------------------
# Diagnostic task
# -------------------------------------------------------------------------
# Purpose:
# Keep the motion sensor streaming continuously while enabling likely sources
# of interference in timed stages. Watch the GUI analog traces for MotSen1-X
# and MotSen1-Y and note which stage makes the trace become jumpy.
#
# Stage order:
# 1. baseline_motion_only
# 2. camera_only
# 3. baseline_after_camera
# 4. led_strip_idle
# 5. baseline_after_led
# 6. speaker_tone_only
# 7. baseline_after_speaker
# 8. camera_led_speaker_static
# 9. camera_led_speaker_dynamic
#
# Dynamic stage:
# Repeatedly changes LED cue position and speaker frequency to mimic normal
# closed-loop task activity more closely than a static output state.


# -------------------------------------------------------------------------
# States and events
# -------------------------------------------------------------------------
states = ['diagnostic']

events = [
    'motion',
    'stage_timer',
    'exercise_timer',
    'session_timer',
]

initial_state = 'diagnostic'


# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
v.motion_threshold = 1
v.stage_duration = 20 * second
v.exercise_period = 1 * second
v.speaker_volume = 15
v.speaker_freq_a = 2000
v.speaker_freq_b = 8000
v.session_duration = 9 * v.stage_duration
v.stage_index = 0
v.exercise_toggle = 0
v.led_positions = (3, 25, 50, 75, 98)
v.led_index = 0


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def stop_loads():
    try:
        hw.cameraTrigger.stop()
    except Exception:
        pass

    try:
        hw.light.all_off()
        hw.light.off()
    except Exception:
        pass

    try:
        hw.speaker.off()
    except Exception:
        pass


def stage_name():
    names = (
        'baseline_motion_only',
        'camera_only',
        'baseline_after_camera',
        'led_strip_idle',
        'baseline_after_led',
        'speaker_tone_only',
        'baseline_after_speaker',
        'camera_led_speaker_static',
        'camera_led_speaker_dynamic',
    )
    return names[v.stage_index]


def enter_stage():
    stop_loads()
    disarm_timer('exercise_timer')
    v.exercise_toggle = 0
    v.led_index = 0

    current_stage = stage_name()
    print('{}, stage={}'.format(get_current_time(), current_stage))

    if current_stage == 'camera_only':
        hw.cameraTrigger.start()

    elif current_stage == 'led_strip_idle':
        hw.light.start()
        hw.light.all_red()
        hw.light.cue_bilateral(True)

    elif current_stage == 'speaker_tone_only':
        hw.speaker.set_volume(v.speaker_volume)
        hw.speaker.sine(v.speaker_freq_a)

    elif current_stage == 'camera_led_speaker_static':
        hw.cameraTrigger.start()
        hw.light.start()
        hw.light.all_red()
        hw.light.cue_bilateral(True)
        hw.speaker.set_volume(v.speaker_volume)
        hw.speaker.sine(v.speaker_freq_a)

    elif current_stage == 'camera_led_speaker_dynamic':
        hw.cameraTrigger.start()
        hw.light.start()
        hw.light.all_red()
        hw.light.cue_bilateral(True)
        hw.speaker.set_volume(v.speaker_volume)
        hw.speaker.sine(v.speaker_freq_a)
        set_timer('exercise_timer', v.exercise_period, True)

    set_timer('stage_timer', v.stage_duration, True)


def advance_stage():
    v.stage_index += 1
    if v.stage_index >= 9:
        print('{}, diagnostic_complete'.format(get_current_time()))
        stop_framework()
    else:
        enter_stage()


def run_dynamic_load():
    v.exercise_toggle = 1 - v.exercise_toggle
    v.led_index = (v.led_index + 1) % len(v.led_positions)

    try:
        hw.light.cue(v.led_positions[v.led_index])
    except Exception:
        pass

    if v.exercise_toggle:
        hw.speaker.sine(v.speaker_freq_a)
        print('{}, dynamic_freq={}'.format(get_current_time(), v.speaker_freq_a))
    else:
        hw.speaker.sine(v.speaker_freq_b)
        print('{}, dynamic_freq={}'.format(get_current_time(), v.speaker_freq_b))

    set_timer('exercise_timer', v.exercise_period, True)


# -------------------------------------------------------------------------
# Run start/end
# -------------------------------------------------------------------------
def run_start():
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_threshold

    if hasattr(hw.motionSensor, 'sensor_x'):
        print('{}, CPI={}'.format(get_current_time(), hw.motionSensor.sensor_x.CPI))
    print('{}, motion_threshold={}'.format(get_current_time(), v.motion_threshold))
    print('{}, stage_duration_s={}'.format(get_current_time(), int(v.stage_duration / second)))
    print('{}, watch_gui=MotSen1-X_and_MotSen1-Y'.format(get_current_time()))

    set_timer('session_timer', v.session_duration, True)
    enter_stage()


def run_end():
    stop_loads()
    hw.motionSensor.stop()
    hw.off()
    print('{}, debug_task_end'.format(get_current_time()))


# -------------------------------------------------------------------------
# State machine
# -------------------------------------------------------------------------
def diagnostic(event):
    if event == 'stage_timer':
        advance_stage()

    elif event == 'exercise_timer':
        if stage_name() == 'camera_led_speaker_dynamic':
            run_dynamic_load()


def all_states(event):
    if event == 'session_timer':
        print('{}, session_timer_expired'.format(get_current_time()))
        stop_framework()

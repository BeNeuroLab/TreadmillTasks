from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'intertrial',
    'wait_for_stillness', # New state
    'running',
    'reward'
]

events = [
    'session_timer',
    'motion',
    'lick',
    'iti_timer',          # Timer for the fixed part of ITI
    'stillness_timer',    # Timer to check for stationarity
    'trial_timeout_timer' # Timer to limit the 'running' state duration
]

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session parameters
v.session_duration = 30 * minute
v.reward_duration = 50 * ms
v.IT_duration = 2 * second  # Fixed duration part of ITI
v.stationary_duration_ms = 2000 * ms # Mouse must be still for this long to start next trial

# Motion to Sound Mapping
v.min_speed_cm_s = 1     # Speed (cm/s) that produces the lowest frequency (avoid 0 to prevent silence if mouse is barely moving but triggering motion events)
v.max_speed_cm_s = 40    # Speed (cm/s) at which the highest frequency is produced (NEEDS CALIBRATION)
v.min_freq_hz = 2000     # Lowest frequency (Hz)
v.max_freq_hz = 10000    # Highest frequency (Hz)
v.target_freq_hz = 8000  # Target frequency (Hz) to trigger reward (NEEDS CALIBRATION)
v.sound_smoothing_factor = 0.3 # Factor for smoothing frequency changes (0-1, 1=no smoothing)


# Motion sensor parameters
v.motion_sensitivity = 5 # Threshold for motion detection (cm). Default for MotionDetector is 1.
                         # The PMW3360DM device class takes this in cm.
v.cpi = hw.motionSensor.sensor_x.CPI if hasattr(hw, 'motionSensor') and hasattr(hw.motionSensor, 'sensor_x') else 1000 # Counts Per Inch, read from sensor or set default
v.inches_to_cm = 2.54
v.sampling_rate = hw.motionSensor.data_chx.sampling_rate if hasattr(hw, 'motionSensor') and hasattr(hw.motionSensor, 'data_chx') else 100 # Hz, from motion sensor setup

# Counters and flags
v.reward_count = 0
v.last_dx_counts = 0 # Store last dx to calculate speed
v.last_dy_counts = 0
v.last_motion_event_time_ms = 0 # Timestamp of the last motion event
v.current_freq_hz = v.min_freq_hz # Initialize
v.trial_timeout_duration = 20 * second # Max duration for a "running" segment

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(15) # Set speaker volume (1-30)
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record()
    hw.motionSensor.threshold = v.motion_sensitivity
    # Update CPI and sampling rate from the instantiated motionSensor object if possible
    if hasattr(hw, 'motionSensor'):
        if hasattr(hw.motionSensor, 'sensor_x') and hasattr(hw.motionSensor.sensor_x, 'CPI'):
            v.cpi = hw.motionSensor.sensor_x.CPI
        if hasattr(hw.motionSensor, 'data_chx') and hasattr(hw.motionSensor.data_chx, 'sampling_rate'):
            v.sampling_rate = hw.motionSensor.data_chx.sampling_rate
            
    print('{}, Session Started. CPI: {}, Sampling Rate: {} Hz'.format(get_current_time(), v.cpi, v.sampling_rate))
    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration, True)
    v.last_motion_event_time_ms = get_current_time() # Initialize for stillness check

def run_end():
    hw.speaker.off()
    hw.reward.stop()
    hw.motionSensor.stop()
    hw.motionSensor.off()
    hw.cameraTrigger.stop()
    hw.off()
    print('{}, Session Ended. Total rewards: {}'.format(get_current_time(), v.reward_count))

# -------------------------------------------------------------------------
# State Machine
# -------------------------------------------------------------------------
def intertrial(event):
    if event == 'entry':
        hw.speaker.off()
        print('{}, Entering Intertrial. Fixed wait: {}s'.format(get_current_time(), v.IT_duration / second))
        set_timer('iti_timer', v.IT_duration)

    elif event == 'iti_timer':
        goto_state('wait_for_stillness')

def wait_for_stillness(event):
    if event == 'entry':
        print('{}, Waiting for stillness ({}ms)'.format(get_current_time(), v.stationary_duration_ms))
        # Reset last motion time to current time to start stillness check *now*
        v.last_motion_event_time_ms = get_current_time()
        set_timer('stillness_timer', v.stationary_duration_ms)
        hw.speaker.off() # Ensure speaker is off

    elif event == 'motion':
        # Mouse moved, reset the stillness timer
        # hw.motionSensor.x and hw.motionSensor.y contain accumulated displacement
        # since the last time the motion event was triggered and reset by the framework
        print('{}, Motion detected during stillness check, resetting timer.'.format(get_current_time()))
        v.last_motion_event_time_ms = get_current_time()
        reset_timer('stillness_timer', v.stationary_duration_ms)

    elif event == 'stillness_timer':
        # No motion for the specified duration
        print('{}, Mouse stationary for {}ms. Starting new trial.'.format(get_current_time(), v.stationary_duration_ms))
        goto_state('running')

    elif event == 'exit':
        disarm_timer('stillness_timer')


def running(event):
    if event == 'entry':
        print('{}, Starting running segment. Max duration: {}s'.format(get_current_time(), v.trial_timeout_duration / second))
        v.current_freq_hz = v.min_freq_hz # Start with min frequency
        hw.speaker.sine(v.current_freq_hz)
        v.last_dx_counts = 0 # Reset accumulated displacement for speed calculation within this state
        v.last_dy_counts = 0
        v.last_motion_event_time_ms = get_current_time() # Initialize for speed calculation
        hw.motionSensor.reset_delta() # Reset internal delta accumulators in the sensor
        set_timer('trial_timeout_timer', v.trial_timeout_duration)

    elif event == 'motion':
        current_time_ms = get_current_time()
        dt_ms = current_time_ms - v.last_motion_event_time_ms
        
        if dt_ms == 0: dt_ms = 1 # Avoid division by zero if events are too rapid

        # hw.motionSensor.x and .y are accumulated counts since last 'motion' event
        # or since reset_delta() was called.
        dx_counts = hw.motionSensor.x
        dy_counts = hw.motionSensor.y # if you want to use 2D speed

        # Calculate displacement in cm for this 'motion' event interval
        # displacement_x_cm = (dx_counts / v.cpi) * v.inches_to_cm
        # displacement_y_cm = (dy_counts / v.cpi) * v.inches_to_cm
        # displacement_total_cm = math.sqrt(displacement_x_cm**2 + displacement_y_cm**2)
        
        # Using only X-axis for simplicity, as often treadmills are 1D
        displacement_cm = (dx_counts / v.cpi) * v.inches_to_cm
        
        # Calculate speed in cm/s
        current_speed_cm_s = abs(displacement_cm / (dt_ms / 1000.0)) # abs for magnitude

        v.last_motion_event_time_ms = current_time_ms
        hw.motionSensor.reset_delta() # Reset for the next motion accumulation

        # Map speed to frequency (linear interpolation)
        target_hz = v.min_freq_hz
        if current_speed_cm_s <= v.min_speed_cm_s:
            target_hz = v.min_freq_hz
        elif current_speed_cm_s >= v.max_speed_cm_s:
            target_hz = v.max_freq_hz
        else:
            speed_range = v.max_speed_cm_s - v.min_speed_cm_s
            if speed_range <= 0: # Avoid division by zero if min_speed >= max_speed
                target_hz = v.min_freq_hz
            else:
                freq_range = v.max_freq_hz - v.min_freq_hz
                target_hz = v.min_freq_hz + \
                    ((current_speed_cm_s - v.min_speed_cm_s) / speed_range) * freq_range
        
        # Smooth the frequency change
        v.current_freq_hz = int((target_hz * v.sound_smoothing_factor) + (v.current_freq_hz * (1-v.sound_smoothing_factor)))

        hw.speaker.sine(v.current_freq_hz)
        print('{}, dx: {}, Speed: {:.2f} cm/s, Target Freq: {} Hz, Smoothed Freq: {} Hz'.format(
            get_current_time(), dx_counts, current_speed_cm_s, int(target_hz), v.current_freq_hz))

        if v.current_freq_hz >= v.target_freq_hz:
            print('{}, Target frequency reached!'.format(get_current_time()))
            goto_state('reward')

    elif event == 'trial_timeout_timer':
        print('{}, Running segment timed out.'.format(get_current_time()))
        goto_state('intertrial')

    elif event == 'exit':
        disarm_timer('trial_timeout_timer')
        hw.speaker.off() # Ensure speaker is off when leaving running state


def reward(event):
    if event == 'entry':
        hw.speaker.off() # Turn off sound during reward
        hw.reward.release()
        v.reward_count += 1
        print('{}, Reward #{} delivered.'.format(get_current_time(), v.reward_count))
        # Transition back to intertrial after reward delivery and a brief pause
        timed_goto_state('intertrial', v.reward_duration + 500*ms)

# -------------------------------------------------------------------------
# Event-handling functions
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'session_timer':
        print('{}, Session Timer Expired'.format(get_current_time()))
        stop_framework()
    elif event == 'lick': # Generic lick handling if needed in all states (e.g. logging)
        print('{}, Lick detected'.format(get_current_time()))
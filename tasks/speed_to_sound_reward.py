from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'intertrial',
    'running',
    'reward'
]

events = [
    'session_timer',
    'motion',  # Event triggered by motion sensor
    'lick'     # Event for reward consumption (optional, but good practice)
]

initial_state = 'intertrial'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session parameters
v.session_duration = 30 * minute
v.reward_duration = 50 * ms   # Duration of reward delivery
v.IT_duration = 3 * second    # Inter-trial interval duration
v.trial_duration = 30 * second # Maximum duration for a "running" segment to reach target

# Motion to Sound Mapping
v.min_speed_cm_s = 0     # Minimum speed (cm/s) that produces the lowest frequency
v.max_speed_cm_s = 50    # Speed (cm/s) at which the highest frequency is produced
v.min_freq_hz = 2000     # Lowest frequency (Hz)
v.max_freq_hz = 12000    # Highest frequency (Hz)
v.target_freq_hz = 10000 # Target frequency (Hz) to trigger reward

# Motion sensor parameters
v.motion_sensitivity = 10 # Threshold for motion detection, adjust as needed. From MotionDetector in _PMW3360DM.py
v.cpi = 100 # Default CPI from PMW3360DM datasheet, adjust if your sensor is different.
v.inches_to_cm = 2.54

# Counters and flags
v.reward_count = 0
v.current_speed_cm_s = 0
v.current_freq_hz = v.min_freq_hz

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(10) # Set speaker volume (1-30)
    hw.reward.reward_duration = v.reward_duration
    hw.motionSensor.record() # Start recording motion data
    hw.motionSensor.threshold = v.motion_sensitivity # Set motion sensor threshold
    # It seems the CPI is readable from the sensor_x object after power_up
    # If you have a different CPI, you might need to set it or adjust calculations.
    # v.cpi = hw.motionSensor.sensor_x.CPI # Or set manually if known
    print('{}, Session Started. CPI: {}'.format(get_current_time(), v.cpi))
    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration, True)

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
    """
    Inter-trial interval.
    Turns off speaker and prepares for the next running segment.
    """
    if event == 'entry':
        hw.speaker.off()
        print('{}, Entering Intertrial. Waiting {}s'.format(get_current_time(), v.IT_duration / second))
        timed_goto_state('running', v.IT_duration)

def running(event):
    """
    Main state where speed is mapped to sound.
    Mouse needs to reach and maintain target frequency.
    """
    if event == 'entry':
        print('{}, Starting running segment. Max duration: {}s'.format(get_current_time(), v.trial_duration / second))
        # Reset current speed and frequency at the start of a running segment
        v.current_speed_cm_s = 0
        v.current_freq_hz = v.min_freq_hz
        hw.speaker.sine(v.current_freq_hz) # Start with min frequency
        timed_goto_state('intertrial', v.trial_duration) # Timeout if target not reached

    elif event == 'motion':
        # Speed is typically dx counts. Convert counts to cm/s.
        # The MotionDetector class stores dx in self.x
        # Sampling rate is also important for converting counts/sample to counts/sec.
        # The motion event itself doesn't directly give speed, rather an accumulation since last event or reset.
        # For simplicity, let's assume hw.motionSensor.x is dx since last 'motion' event.
        # The sampling rate of the motion sensor is set in hardware_definition.py, e.g., 100 Hz.
        # So, dx_counts_per_sample = hw.motionSensor.x
        # dx_cm_per_sample = (dx_counts_per_sample / v.cpi) * v.inches_to_cm
        # sampling_interval_s = 1 / hw.motionSensor.sampling_rate (e.g. 1/100 = 0.01s)
        # v.current_speed_cm_s = dx_cm_per_sample / sampling_interval_s
        # For this example, let's simplify and assume hw.motionSensor.x roughly gives a speed indicator.
        # A more robust way would be to accumulate distance over time.
        # The MotionDetector has sensor_x.CPI and sampling_rate attributes.

        dx_counts = hw.motionSensor.x # Counts since last motion event above threshold
        # dy_counts = hw.motionSensor.y # If using y-axis movement as well

        # Assuming motion events occur at the sampling rate when mouse is moving
        # This is a simplification. True speed requires dx/dt.
        # The 'motion' event in pyControl triggers when displacement exceeds a threshold,
        # not at every sample. The stored hw.motionSensor.x/y are accumulated counts.
        # For a simple mapping, we can use the magnitude of these counts.
        # A better approach might involve calculating speed over the last N samples
        # or using the timestamp of the 'motion' event to calculate dt.

        # Simplified approach: use the magnitude of dx as a proxy for current speed.
        # This value will need calibration and scaling.
        # The PMW3360DM sensor has a sampling rate, but the 'motion' event in pyControl
        # is triggered when accumulated displacement exceeds a threshold.
        # We need to estimate speed. Let's assume the 'motion' event gives us displacement (dx)
        # over the time since the last 'motion' event or a fixed small dt.
        # For a quick start, let's scale dx directly, assuming motion events are frequent enough.

        # Let's assume dx is counts per a small, somewhat fixed interval related to motion event triggering
        # speed_metric = abs(dx_counts) # Use absolute displacement

        # A more accurate way: The Analog_input class (parent of MotionDetector) has a timer_ISR
        # that reads samples at `sampling_rate`. `hw.motionSensor.x` and `hw.motionSensor.y`
        # are updated with the *accumulated* displacement since the last reset_delta() call
        # *when the threshold is crossed*.
        # To get instantaneous speed, we'd need to access the raw _delta_x, _delta_y per sample.
        # The `motion` event gives `hw.motionSensor.x` which is the *total displacement*
        # that triggered the event. To get speed, we need dt for this displacement.
        # Let's use a simplification for now: assume `hw.motionSensor.x` is proportional to recent speed.

        # Convert dx_counts to cm. CPI is counts per inch.
        displacement_cm = (dx_counts / v.cpi) * v.inches_to_cm
        
        # Simplistic speed: assume this displacement happened over the motion sensor's sampling interval
        # This is not entirely accurate as 'motion' event is threshold-based.
        # A better way would be to use the time between 'motion' events.
        # Or, better yet, get velocity directly if the sensor/firmware provides it.
        # The `Rotary_encoder` class calculates velocity as `counter_change * self.sampling_rate`.
        # The `MotionDetector` class calculates `_delta_x` and `_delta_y` per sample in `read_sample`.
        # However, the 'motion' event itself provides `self.x` which is `self.delta_x` (accumulated).

        # Let's assume, for simplicity, that each 'motion' event roughly corresponds to displacement over 1/sampling_rate.
        # This will likely need significant tuning.
        sampling_interval = 1.0 / hw.motionSensor.data_chx.sampling_rate # from Analog_input parent
        v.current_speed_cm_s = abs(displacement_cm / sampling_interval) # abs for magnitude


        # Map speed to frequency (linear interpolation)
        if v.current_speed_cm_s <= v.min_speed_cm_s:
            v.current_freq_hz = v.min_freq_hz
        elif v.current_speed_cm_s >= v.max_speed_cm_s:
            v.current_freq_hz = v.max_freq_hz
        else:
            speed_range = v.max_speed_cm_s - v.min_speed_cm_s
            freq_range = v.max_freq_hz - v.min_freq_hz
            v.current_freq_hz = v.min_freq_hz + \
                ((v.current_speed_cm_s - v.min_speed_cm_s) / speed_range) * freq_range
        
        v.current_freq_hz = int(v.current_freq_hz) # Ensure integer frequency
        hw.speaker.sine(v.current_freq_hz)
        print('{}, Speed: {:.2f} cm/s, Freq: {} Hz'.format(get_current_time(), v.current_speed_cm_s, v.current_freq_hz))

        if v.current_freq_hz >= v.target_freq_hz:
            print('{}, Target frequency reached!'.format(get_current_time()))
            goto_state('reward')

    elif event == 'lick':
        # Optional: reset trial timer on lick if you want to discourage licking when not at target
        # reset_timer('trial_timer', v.trial_duration) # Example
        pass


def reward(event):
    """
    Reward delivery state.
    """
    if event == 'entry':
        hw.speaker.off() # Turn off sound during reward
        hw.reward.release()
        v.reward_count += 1
        print('{}, Reward #{} delivered.'.format(get_current_time(), v.reward_count))
        # Transition back to intertrial after reward delivery and a brief pause
        timed_goto_state('intertrial', v.reward_duration + 500*ms) # Add 500ms post-reward pause

    elif event == 'lick':
        # Lick during reward or post-reward pause, can be ignored or logged
        pass

# -------------------------------------------------------------------------
# Event-handling functions
# -------------------------------------------------------------------------
def all_states(event):
    """
    Executed before state-specific code. Handles session timer.
    """
    if event == 'session_timer':
        print('{}, Session Timer Expired'.format(get_current_time()))
        stop_framework()
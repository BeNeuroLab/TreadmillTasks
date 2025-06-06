from pyControl.utility import *
import hardware_definition as hw
from devices import *
import math

# -------------------------------------------------------------------------
# States and Events
# -------------------------------------------------------------------------
states = [
    'running',
    'stopped'
]

events = [
    'session_timer',
    'update_timer',  # Timer for updating frequency based on raw motion data
    'motion',        # Still available for threshold-based events if needed
    'stop_button'
]

initial_state = 'running'

# -------------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------------
# Session parameters
v.session_duration = 10 * minute
v.update_interval = 10 * ms  # How often to update frequency (10ms = 100Hz)

# Motion to frequency mapping
v.displacement_scale = 100    # Scale factor for raw displacement values
v.min_freq_hz = 1000         # Frequency when no motion
v.max_freq_hz = 15000        # Maximum frequency
v.freq_range = v.max_freq_hz - v.min_freq_hz

# Smoothing parameters
v.smoothing_factor = 0.3     # 0-1, higher = less smoothing
v.current_freq = v.min_freq_hz
v.last_x = 0
v.last_y = 0

# Motion sensor parameters
v.cpi = 100  # Will be updated from actual sensor in run_start

# -------------------------------------------------------------------------
# Run Start/End
# -------------------------------------------------------------------------
def run_start():
    hw.speaker.set_volume(15)
    hw.motionSensor.record()
    
    # Get actual CPI from sensor
    if hasattr(hw.motionSensor, 'sensor_x'):
        v.cpi = hw.motionSensor.sensor_x.CPI
    
    # Start with minimum frequency
    hw.speaker.sine(v.min_freq_hz)
    
    print('{}, Session Started. CPI: {}, Update Rate: {} Hz'.format(
        get_current_time(), v.cpi, 1000/v.update_interval))
    
    hw.cameraTrigger.start()
    set_timer('session_timer', v.session_duration, True)
    set_timer('update_timer', v.update_interval, True)

def run_end():
    hw.speaker.off()
    hw.motionSensor.stop()
    hw.motionSensor.off()
    hw.cameraTrigger.stop()
    hw.off()
    print('{}, Session Ended.'.format(get_current_time()))

# -------------------------------------------------------------------------
# State Machine
# -------------------------------------------------------------------------
def running(event):
    if event == 'entry':
        print('{}, Motion-to-frequency mapping active'.format(get_current_time()))
        
    elif event == 'update_timer':
        # Access raw motion data directly from the sensor
        # These values are accumulated since last read
        raw_dx = hw.motionSensor._delta_x
        raw_dy = hw.motionSensor._delta_y
        
        # Calculate magnitude of movement
        magnitude = math.sqrt(raw_dx**2 + raw_dy**2)
        
        # Map magnitude to frequency
        # Adjust displacement_scale to tune sensitivity
        scaled_magnitude = magnitude / v.displacement_scale
        
        # Clamp to 0-1 range
        if scaled_magnitude > 1:
            scaled_magnitude = 1
        
        # Linear mapping to frequency
        target_freq = v.min_freq_hz + (scaled_magnitude * v.freq_range)
        
        # Apply smoothing
        v.current_freq = int((target_freq * v.smoothing_factor) + 
                            (v.current_freq * (1 - v.smoothing_factor)))
        
        # Update speaker frequency
        hw.speaker.sine(v.current_freq)
        
        # Optional: print for debugging (comment out for normal use)
        if magnitude > 0:  # Only print when there's movement
            print('{}, Raw: ({}, {}), Mag: {:.1f}, Freq: {} Hz'.format(
                get_current_time(), raw_dx, raw_dy, magnitude, v.current_freq))
    
    elif event == 'stop_button':
        goto_state('stopped')

def stopped(event):
    if event == 'entry':
        hw.speaker.off()
        print('{}, Stopped - press button to resume'.format(get_current_time()))
    
    elif event == 'stop_button':
        hw.speaker.sine(v.current_freq)
        goto_state('running')

# -------------------------------------------------------------------------
# Event handlers
# -------------------------------------------------------------------------
def all_states(event):
    if event == 'session_timer':
        print('{}, Session Timer Expired'.format(get_current_time()))
        stop_framework()
    elif event == 'motion':
        # This still fires when accumulated motion exceeds threshold
        # Can be used for additional logic if needed
        pass
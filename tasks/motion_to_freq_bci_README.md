# Motion to Frequency BCI Task

## Overview
The `motion_to_freq_bci.py` task is a brain-computer interface (BCI) controlled auditory feedback task where the animal's neural activity (decoded by the BCI) controls frequency changes in real-time. The task uses motion detection to initiate BCI control and implements octave-based frequency boundaries for speaker updates.

## Task Flow

### States
1. **intertrial**: Waiting period between trials
2. **trial**: Active BCI control period
3. **reward**: Reward delivery state
4. **stopped**: Paused state (toggle with stop button)

### State Transitions
```
intertrial → trial → reward → intertrial
     ↓                           ↑
     └───────(timeout)───────────┘
```

## Key Features

### 1. BCI Communication Protocol
The task sends specific integer values to the BCI system at different events:
- `1`: Trial start (when entering trial state)
- `2`: First motion detected (sent once per trial)
- `3`: Reward state entered
- `4`: Trial end (when entering intertrial state)

### 2. Motion-Gated Trial Initiation
- Trials only start after a period of no motion (stillness)
- Requires `v.motion_wait_time` (2 seconds) without motion after the minimum intertrial duration
- This ensures the animal is stationary before beginning BCI control

### 3. Frequency Control via BCI
- BCI sends frequency values through `cursor_update` events
- Frequency updates are received via `hw.bci_link.spk`
- Each update is logged: `{frequency}, cursor_update_freq`

### 4. Octave Boundary Constraint
- Speaker frequency only updates when crossing octave boundaries
- Octave boundaries are powers of 2 (e.g., 2000-4000 Hz, 4000-8000 Hz, 8000-16000 Hz)
- This creates discrete frequency "zones" rather than continuous updates
- Prevents small fluctuations in BCI output from causing audible changes

### 5. Goal Detection
- Target frequency: 12000 Hz
- When BCI frequency ≥ goal frequency:
  - Goal tone plays for 1 second
  - Transitions to reward state
  - Animal has 5 seconds to lick for reward

## Parameters

### Timing Parameters
- `session_duration`: 30 minutes
- `intertrial_duration`: 4 seconds (minimum)
- `trial_timeout`: 15 seconds (maximum trial length)
- `motion_wait_time`: 2 seconds (required stillness)
- `reward_duration`: 30 ms (solenoid open time)
- `target_present_duration`: 1 second (goal tone playback)

### Frequency Parameters
- `start_freq_hz`: 2000 Hz (initial frequency)
- `goal_freq_hz`: 12000 Hz (target frequency)
- `num_steps`: 5 (discrete frequency steps - currently unused in BCI mode)

### Motion Detection
- `motion_threshold`: 10 (motion sensor threshold)
- `cpi`: Counts per inch (read from motion sensor)

## Trial Sequence

1. **Intertrial Phase**
   - Send `4` to BCI (trial end signal)
   - Wait for minimum intertrial duration
   - Monitor for motion - reset wait timer if motion detected
   - After stillness period, proceed to trial

2. **Trial Phase**
   - Send `1` to BCI (trial start signal)
   - Play starting frequency (2000 Hz)
   - On first motion: send `2` to BCI
   - Receive frequency updates from BCI via `cursor_update`
   - Update speaker only when crossing octave boundaries
   - Continue until goal reached or timeout

3. **Reward Phase**
   - Send `3` to BCI (reward signal)
   - Wait up to 5 seconds for lick
   - If lick detected: deliver reward, increment counter
   - Return to intertrial

## Data Logging

The task prints the following information:

### Session Start
- CPI (counts per inch)
- Motion threshold
- Motion wait time
- Trial timeout
- Start and goal frequencies
- Number of steps

### During Trial
- `first_motion_sent_to_BCI`: When first motion triggers BCI control
- `{freq}, cursor_update_freq`: Each BCI frequency update
- `{freq}, frequency_updated`: When speaker frequency changes (octave crossing)
- `{goal_freq}, target_reached`: When goal frequency achieved

### Trial Events
- `trial_start`: Beginning of each trial
- `reward_state_entered`: Entering reward phase
- `{n}, reward_number`: Cumulative reward count

### Session End
- Total rewards delivered

## Implementation Notes

1. **Octave Boundary Calculation**
   - Lower boundary = 2^floor(log2(frequency))
   - Only updates speaker when crossing these boundaries
   - Reduces speaker updates while maintaining perceptual relevance

2. **BCI Integration**
   - Uses UART communication via `hw.bci_link`
   - Receives 2-byte integers representing frequency
   - Sends status integers to coordinate with BCI system

3. **Motion Sensor Role**
   - Gates trial initiation (stillness requirement)
   - Triggers BCI control start (first motion → send 2)
   - Does not directly control frequency (unlike non-BCI version)

## Differences from Non-BCI Version

1. **Frequency Control**: BCI updates instead of distance-based calculation
2. **Motion Role**: Only for gating and triggering, not frequency mapping
3. **Update Logic**: Octave boundaries instead of distance thresholds
4. **Communication**: Active bidirectional BCI communication
5. **Data Source**: Neural decoding rather than movement accumulation
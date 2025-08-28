# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TreadmillTasks is a behavioral neuroscience experiment control system built on the PyControl framework. It controls spherical treadmill experiments using MicroPython on pyboard D-series breakout boards.

## Development Setup

1. **Environment Setup**: 
   ```bash
   conda env create -f env.yml
   conda activate pycontrol
   ```

2. **Running the GUI**:
   ```bash
   python pyControl_GUI.py
   ```

## Architecture

The codebase follows a modular architecture:

- **tasks/**: Behavioral task definitions as state machines
  - Tasks use numbered prefixes (0-, 1-, 2-) to indicate training protocol order
  - Each experiment typically has its own git branch
  - Follow conventions in `tasks/conventions.md` for naming states, events, and prints

- **devices/**: Hardware device drivers for sensors, actuators, and custom boards
  - Key devices: motion sensors, lick sensors, solenoids, speakers, LEDs
  - All devices inherit from pyControl device classes

- **gui/**: PyQt5-based GUI with three main tabs:
  - Run Task: Execute individual behavioral tasks
  - Experiments: Configure multi-subject/multi-session experiments
  - Setups: Manage hardware configurations

- **pyControl/**: Core framework modules for state machines, hardware abstraction, and timing

## Key Conventions

### State Names (required):
- `trial`: Main experimental state where stimuli are presented
- `intertrial`: Gap between trials

### State Names (recommended):
- `reward`: Triggered when reward is delivered
- `timeout`: Triggered after disengagement
- `penalty`: Triggered by unwanted behavior
- `free`: Baseline uninterrupted behavior
- `cursor_match`: When cursor matches target position

### Event Names:
- `session_timer`: Ends the session
- `trial_timer`: Controls trial duration
- `IT_timer`: Controls intertrial duration
- `lick`: Lick sensor activation
- `motion`: Motion sensor triggers (every 5cm displacement)
- `cursor_update`: Updates cursor position

### Print Conventions:
- Format: `print("val, message")`
- Key prints: `reward_number`, `spk_direction`, `led_direction`, `sol_direction`

## Testing

Tests are organized by scope:
- **Framework tests** (`tests/Framework tests/`): Test core pyControl functionality
- **Board tests** (`tests/Board tests/`): Hardware-specific tests requiring physical connections
- **Task tests** (`tasks/tests/`): Behavioral task validation

Tests run directly on the microcontroller - upload and execute via the GUI.

## Important Notes

- No traditional build system - code runs directly on MicroPython boards
- No linting or type checking commands - MicroPython has limited tooling
- Hardware configuration is defined in `config/hardware_definition.py`
- User-specific paths are configured in `config/user_paths.json`
- Data is automatically logged to the `data/` directory during experiments
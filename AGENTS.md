# Repository Guidelines

## Project Structure & Module Organization
- `pyControl/`: Core framework (state machines, hardware, audio).
- `gui/` and `pyControl_GUI.py`: Qt-based desktop GUI entrypoint and views.
- `devices/`: Device drivers and breakout boards.
- `tasks/`: Behavioral task scripts (see numbered patterns) and `tasks/tests/` examples.
- `com/`: Board communication helpers.
- `config/`: User/config paths, GUI settings, hardware definitions.
- `tools/`: Utilities for data import, plotting, and syncing.
- `tests/`: Hardware/framework smoke tests; many require a connected board.
- `data/`, `experiments/`: User data and experiment files (gitignored where appropriate).

## Build, Test, and Development Commands
- Create env: `conda env create -f env.yml` (name: `pycontrol`).
- Activate: `conda activate pycontrol`.
- Run GUI: `python pyControl_GUI.py` (launches main app).
- Lint (optional): `python -m pyflakes <path>` if installed; otherwise follow PEP 8 manually.
- Quick device/task trials: run minimal scripts in `tests/` or launch tasks via the GUI.

## Coding Style & Naming Conventions
- Python 3, PEP 8, 4-space indentation.
- Modules/functions: `snake_case`; Classes: `CamelCase`.
- Tasks: prefix with sequence numbers and concise verbs, e.g., `0-lick-triggered-reward.py`, `3-run-to-stim.py`.
- Keep functions small; prefer pure helpers in `pyControl/` and hardware I/O in `devices/`.

## Testing Guidelines
- Hardware tests live under `tests/` (e.g., `Board tests/stepper_driver_test.py`).
- Add focused scripts named `*_test.py` for board/device checks; document required setup at top of file.
- For task validation, add runnable examples under `tasks/tests/`.
- Run tests via the GUI where interaction is needed; many scripts expect connected hardware.

## Commit & Pull Request Guidelines
- Commit style: Prefer Conventional Commits (e.g., `feat(tasks): add teleportation variant`).
- Scope keywords: `tasks`, `gui`, `devices`, `pyControl`, `config`, `tools`.
- PRs: clear description, link issues, list hardware used, and include screenshots/GIFs for GUI changes.
- Update `env.yml` when adding deps and note any migration instructions.

## Security & Configuration Tips
- Never commit user data; paths are set in `config/user_paths.json` and `config/paths.py`.
- USB permissions/ports vary by OS; verify detection in GUI (Ports list) before running tasks.

# how to name tasks

## Tasks

- each experiment to have a branch
- keep the task names informative
- use a docstring in the first line of the task file to explicitly describe what the task is doing

## States

- the following state names must exist:
  - a state called `trial` where the important things happen 
  - a state called `intertrial` that acts as a intertrial period/ gap

- the following state names are recommended
  - a state called `reward` that starts with delivery of reward, i.e., opening of the solenoid
  - a state called `timeout` that is triggered after a period of disengagement from the task
  - a state called `penalty` that is triggered by unwanted behaviour, e.g., licking at the wrong time
  - a state called `free` that is a baseline for uninterrupted behaviour
  - a state called `cursor_match` for period of time when the cursor matches the target
 
## Events

- an event called `session_timer` that triggers the end of the session
- an event called `trial_timer` that specify the duration of the trial
- an event called `IT_timer` that specify the duration of the intertrial
- an event called `cursor_update` that times the updating of the cursor, in both behavioural sessions and BCI.
- an event called `lick` that is self-explanatory!
- an event called `motion` that the sensors generate every 5cm of displacement

## Prints

If printing a value, print statement should be like `print("val, message")`

- a print message called `reward_number` a statement for the accumulative number of released rewards
- a print message called `spk_direction` to specify which speaker is active
- a print message called `led_direction` to specify which LED is on
- a print message called `sol_direction` to specify the ID of the activated solenoid


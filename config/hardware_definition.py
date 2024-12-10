from devices import *

board = Breakout_dseries_1_6()

# Instantiate Devices.
bci_link = UARTlink('cursor_update', timer_freq=100)

#motionSensor = MotionDetector(name='MotSen1', event='motion',
#                              reset=board.port_1.DIO_C,
#                              cs1=board.port_2.DIO_A,
#                              cs2=board.port_2.DIO_B,
#                              calib_coef=1, threshold=1, sampling_rate=100)

light = LEDStim()
light.all_off()

lickometer = Lickometer(lick_port=board.port_6, sol_port=board.port_7, rising_event_A='lick', debounce=5,pull="up")
reward = Reward(lickometer.SOL_1 , reward_duration=50)

# sound = AudioStim(board.port_11)
speaker = Audio_board(board.port_8)

cameraTrigger = CameraPulse(pin=board.port_1.POW_B, trigger_rate=100, duty_cycle=50)

_sync_output = Rsync(pin=board.port_1.POW_A, event_name='rsync', mean_IPI=5000, pulse_dur=50)

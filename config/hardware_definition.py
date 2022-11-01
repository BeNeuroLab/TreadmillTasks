from devices import *

board = Breakout_dseries_1_6()

# Instantiate Devices.
usb_uart = USB_UART('audio_freq')

motionSensor = MotionDetector(name='MotSen1', event='motion',
                              reset=board.port_1.DIO_C,
                              CS1=board.port_2.DIO_A,
                              CS2=board.port_2.DIO_B,
                              calib_coef=1, threshold=1, sampling_rate=100)

odourDelivery = ParallelOdourRelease()

lickometer = Lickometer(port=board.port_6, rising_event_A='lick', falling_event_A='lick_off',
                        rising_event_B='_lick_2___', falling_event_B='_lick_2_off___', debounce=5)

rewardSol = lickometer.SOL_1  # has two methods: on() and off()

speaker = Audio_board(board.port_7)

cameraTrigger = CameraPulse(pin=board.port_3.DIO_A, trigger_rate=100, duty_cycle=50)

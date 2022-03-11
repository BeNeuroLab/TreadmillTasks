from devices import *

board = Breakout_dseries_1_6()

# Instantiate Devices.

motionSensor = MotionDetector_2ch(name='MotSen1', event='motion',
                                  reset1=board.port_3.DIO_B,
                                  reset2=board.port_4.DIO_C,
                                  CS1=board.port_3.DIO_A,
                                  CS2=board.port_1.DIO_C,
                                  calib_coef=1, threshold=1, sampling_rate=100)

# in each direction, Odour0 is always the clean air, Odour1 is the odourant,...
odourDelivery = ParallelOdourRelease(5, 2,
                                     board.port_1.POW_A, board.port_1.POW_B,    # Dir1
                                     board.port_2.POW_A, board.port_2.POW_B,    # Dir2
                                     board.port_3.POW_A, board.port_3.POW_B,    # Dir3
                                     board.port_4.DIO_A, board.port_4.DIO_B,    # Dir4
                                     board.port_4.POW_A, board.port_4.POW_B)    # Dir5

lickometer = Lickometer(port=board.port_6, rising_event_A='lick', falling_event_A='lick_off',
                        rising_event_B='_lick_2___', falling_event_B='_lick_2_off___', debounce=5)

rewardSol = lickometer.SOL_1  # has two methods: on() and off()

speaker = Audio_board(board.port_7)

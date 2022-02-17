from devices import *

board = Breakout_dseries_1_6()

# Instantiate Devices.

motionSensor = MotionDetector_2ch(name='MotSen1', event='motion',
                                  calib_coef=1, threshold=1, sampling_rate=100, reset1=board.port_3.DIO_B,
                                  sensor2pins={'CS': board.port_4.DIO_B, 'MI': board.port_4.DIO_C, 'MO': board.port_5.DIO_A, 'SCK': board.port_5.DIO_B, 'reset':board.port_4.DIO_A})

# in each direction, Odour0 is always the clean air, Odour1 is the odourant,...
# odourDelivery = ParallelOdourRelease(5, 2,
#                                      board.port_1.DIO_C, board.port_1.POW_A,    # Dir1
#                                      board.port_1.POW_B, board.port_4.DIO_A,    # Dir2
#                                      board.port_4.DIO_B, board.port_4.DIO_C,    # Dir3
#                                      board.port_5.DIO_A, board.port_5.DIO_B,    # Dir4
#                                      board.port_5.POW_A, board.port_5.POW_B)    # Dir5

# lickometer = Lickometer(port=board.port_6, rising_event_A='lick', falling_event_A='lick_off',
#                         rising_event_B='_lick_2___', falling_event_B='_lick_2_off___', debounce=5)

# rewardSol = lickometer.SOL_1  # has two methods: on() and off()

# speaker = Audio_board(board.port_7)

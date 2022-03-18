from pyControl.utility import *
import hardware_definition as hw

states = ['init']
events = ['audio_freq']
initial_state = 'init'

def init(event):
    if event == 'entry':
        print('entering init')
    elif event == 'exit':
        print('exiting init')
    elif event == 'read_uart':
        print(hw.usb_uart.freq)
    
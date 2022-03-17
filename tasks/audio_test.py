from pyControl.utility import *
import hardware_definition as hw

states = ['init']
events = ['read_uart']
initial_state = 'init'


hw.usb_uart.start_test()

def init(event):
    if event == 'entry':
        print('entering init')
    elif event == 'exit':
        print('exiting init')
    elif event == 'read_uart':
        print(hw.usb_uart.output)
    
from pyControl.hardware import *
from pyb import UART
from machine import Timer


class UARTlink(IO_object):
    def __init__(self, name, timer_freq = 100):
        """
        UART device class for Port12
        name: the framework Event name
        timer_freq: int, frequency of the timer, twice the client frequency
        """
        self.uart = UART(1, 9600)  # uart1=port 12, init with given baudrate
        self.uart.init(9600, bits=8, parity=None, stop=1)
        self.buffer = bytearray(8)
        self.name = name
        self.timer_freq = timer_freq
        assign_ID(self)
        self.timer = pyb.Timer(available_timers.pop())
        self.timestamp = 0
        self.spk = 0
        self.prev_spk = 0

    def _timer_ISR(self, t):
        if self.uart.any() > 0:  # there is a message
            self.uart.readinto(self.buffer, 2)
            self.spk = int.from_bytes(self.buffer, 'little')
            if self.spk != self.prev_spk:
                self.timestamp = fw.current_time
                interrupt_queue.put(self.ID)
                self.prev_spk = self.spk

    def _initialise(self):
        self.timer.init(freq=self.timer_freq)   # this should be 2*(client frequency)
        self.timer.callback(self._timer_ISR)

    def _process_interrupt(self):
        fw.event_queue.put((self.timestamp, fw.event_typ, fw.events[self.name]))

from pyControl.hardware import *
from pyb import UART
from machine import Timer


class UARTlink(IO_object):
    def __init__(self, name, timer_freq = 100):
        """
        uart device class: for BCI comm and for led strip
        whatever integer is recieved from the BCI computer, is passed to the LED strip using the `uart_led`
        name: the framework Event name for BCI cursor changing value
        timer_freq: int, frequency of the timer, twice the client frequency
        """
        self.uart_bci = UART(1, 9600)  # uart1=port 12, init with given baudrate
        self.uart_led = UART(4, 9600)  # uart1=port 10, init with given baudrate
        
        self.uart_bci.init(9600, bits=8, parity=None, stop=1)
        self.uart_led.init(9600, bits=8, parity=None, stop=1)

        self.buffer = bytearray(8)
        self.name = name
        self.timer_freq = timer_freq
        assign_ID(self)
        self.timer = pyb.Timer(available_timers.pop())
        self.timestamp = 0
        self.spk = 0
        self.prev_spk = 0

    def _timer_ISR(self, t):
        if self.uart_bci.any() > 0:  # there is a message
            self.uart_bci.readinto(self.buffer, 2)
            self.spk = int.from_bytes(self.buffer, 'little')
            if self.spk != self.prev_spk:
                self.timestamp = fw.current_time
                interrupt_queue.put(self.ID)
                self.uart_led.write(self.buffer)
                self.prev_spk = self.spk

    def _initialise(self):
        self.timer.init(freq=self.timer_freq)
        self.timer.callback(self._timer_ISR)

    def _process_interrupt(self):
        fw.event_queue.put((self.timestamp, fw.event_typ, fw.events[self.name]))

    def send_int(self, value: int) -> None:
        """Send a 2-byte little-endian integer to the host."""
        self.uart_bci.write(value.to_bytes(2, 'little'))

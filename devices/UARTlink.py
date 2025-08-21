import pyControl.hardware as _h
from pyb import UART, Timer


class UARTlink(_h.IO_object):
    def __init__(self, bci_event_name, timer_freq = 100, do_led_strip = False):
        """
        uart device class: for BCI comm and for led strip
        whatever integer is recieved from the BCI computer, is passed to the LED strip using the `uart_led`
        name: the framework Event name for BCI cursor changing value
        timer_freq: int, frequency of the timer, twice the client frequency
        """
        self.uart_bci = None
        self.uart_led = None
        self.do_led_strip = do_led_strip

        self.buffer = bytearray(8)
        self.name = bci_event_name
        self.timer_freq = timer_freq
        _h.assign_ID(self)
        self.timer = Timer(_h.available_timers.pop())
        self.timestamp = 0
        self.spk = 0
        self.prev_spk = 0

    def _timer_ISR(self, t):
        if self.uart_bci.any() > 0:  # there is a message
            self.uart_bci.readinto(self.buffer, 2)
            self.spk = int.from_bytes(self.buffer, 'little')
            if self.spk != self.prev_spk:
                self.timestamp = fw.current_time
                _h.interrupt_queue.put(self.ID)
                self.prev_spk = self.spk
                if self.do_led_strip:
                    self.uart_led.write(self.buffer)

    def start(self):
        "this method must be called in the `run_start` of any task file"
        self.uart_bci = UART(1, 9600)  # uart1=port 12, init with given baudrate        
        self.uart_bci.init(9600, bits=8, parity=None, stop=1)

        if self.do_led_strip:
            self.uart_led = UART(4, 9600)  # uart1=port 10, init with given baudrate
            self.uart_led.init(9600, bits=8, parity=None, stop=1)

        self.timer.init(freq=self.timer_freq)
        self.timer.callback(self._timer_ISR)

    def stop(self):
        self.uart_bci.deinit()
        self.timer.deinit()
        if self.do_led_strip:
            self.uart_led.deinit()

    def _process_interrupt(self):
        _h.fw.event_queue.put((self.timestamp, _h.fw.event_typ, _h.fw.events[self.name]))

    def bci_send_int(self, value: int) -> None:
        """Send a 2-byte little-endian integer to the host."""
        self.uart_bci.write(value.to_bytes(2, 'little'))


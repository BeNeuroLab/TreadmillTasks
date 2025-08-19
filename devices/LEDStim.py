import pyb, machine, time
import pyControl.hardware as _h



class LedStirp(IO_object):
    def __init__(self):
        """
        LED strip control class
        """
    def cue(self, dir_percent:int):
        """turn on the LED corresponding to the given percentagedirection
        It MUST be between 0 and 100
        """
        assert 0 <= dir_percent <= 100, "Invalid direction"
        self.send_int(dir_percent)

    def start(self):
        self.uart_led = UART(4, 9600)  # uart1=port 10, init with given baudrate
        self.uart_led.init(9600, bits=8, parity=None, stop=1)

    def stop(self):
        self.uart_led.deinit()

    def send_int(self, value: int) -> None:
        """Send a 2-byte little-endian integer to the host."""
        self.uart_led.write(value.to_bytes(2, 'little'))


class LEDStim:
    "LED stimuli."
    def __init__(self):
        "initialise the LED pins"
        pins = {1:'W45',    # Dir1
                2:'W43',    # Dir2
                3:'W24',    # Dir3
                4:'W32',    # Dir4
                5:'W30'}    # Dir5
        # this variable indicates the POW pins used so that their logic level is inverted automatically.
        powerlines = ('W16', 'W50', 'W60', 'W22','W30','W32')
        self.LEDs = {}
        self.active = []

        for direction, pin in pins.items():
            self.LEDs[direction] = _h.Digital_output(pin=pin, inverted=pin in powerlines, pulse_enabled=True)
            self.LEDs[direction].off()

    def all_off(self):
        "turn off all LEDs"
        for led in self.LEDs.values():
            led.off()
        self.active = []

    def all_on(self):
        "turn on all LEDs"
        for led in self.LEDs.values():
            led.on()
        self.active = list(self.LEDs.keys())

    def cue(self, direction:int):
        "turn on the LED corresponding to the given direction"
        self.all_off()
        self.LEDs[direction].on()
        self.active = [direction]

    def cue_array(self, arr:list):
        "turn on the LEDs corresponding to the given directions in `arr`"
        self.all_off()
        for d in arr:
            self.LEDs[d].on()
            self.active.append(d)

    def blink(self, direction:int, freq=10, n_pulses:int =20):
        "blink the LED corresponding to the given direction for the given number of pulses"
        self.LEDs[direction].pulse(freq=freq, duty_cycle=50, n_pulses=n_pulses)

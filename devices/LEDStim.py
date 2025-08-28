import pyb
import pyControl.hardware as _h


class LedStrip(_h.IO_object):
    """
    LED strip control class
    based on:
    https://github.com/CeciliaGallego/dostar-led-stip/blob/main/code.py
    """

    def cue(self, dir_percent:int):
        """turn on the LED corresponding to the given percentagedirection
        It MUST be between 0 and 100
        """
        assert 1 <= dir_percent <= 100, "Invalid direction"
        self.send_int(dir_percent)

    def start(self):
        "this method must be called in the `run_start` of any task file"
        self.uart_led = pyb.UART(4)  # uart4=port 10
        self.uart_led.init(baudrate=9600, bits=8, parity=None, stop=1)
        self.all_red()
        self.cue_bilateral(True)

    def all_red(self):
        "turn off all LEDs, everything red"
        self.send_int(201)

    def all_off(self):
        "turn off all LEDs"
        self.send_int(200)

    def cue_bilateral(self, bilatral = True):
        "switch whether cue is symmetrical (central target) or not"
        if bilatral:
            self.send_int(210)
        else:
            self.send_int(211)

    def send_int(self, value: int) -> None:
        """Send a 2-byte little-endian integer to the host."""
        self.uart_led.write(value.to_bytes(1, 'little'))

    def off(self):
        try:  # in case it hasn't been initialised
            self.all_off()
            self.uart_led.deinit()
        except:
            pass



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

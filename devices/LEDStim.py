import pyb, machine, time
import pyControl.hardware as _h


class LEDStim:
    "LED stimuli."
    def __init__(self):
        """PINS should be exactly `Ndirections` strings"""

        pins = {1:'W45',    # Dir1
                2:'W43',    # Dir2
                3:'W24',    # Dir3
                4:'W32',    # Dir4
                5:'W30'}    # Dir5
        # this variable indicates the POW pins used so that their logic level is inverted automatically.
        powerlines = ('W16', 'W50', 'W60', 'W22','W30','W32')
        self.LEDs = {}
        for direction, pin in pins.items():
            self.LEDs[direction] = _h.Digital_output(pin=pin, inverted=pin in powerlines)
            self.LEDs[direction].off()

    def all_off(self):
        "turn off all LEDs"
        for led in self.LEDs.values():
            led.off()

    def all_on(self):
        "turn on all LEDs"
        for led in self.LEDs.values():
            led.on()

    def cue(self, direction:int):
        "turn on the LED corresponding to the given direction"
        for d, led in self.LEDs.items():
            if d == direction:
                led.on()
            else:
                led.off()

    def cue_array(self, arr:list):
        "turn on the LEDs corresponding to the given directions in `arr`"
        self.all_off()
        for d in arr:
            self.LEDs[d].on()

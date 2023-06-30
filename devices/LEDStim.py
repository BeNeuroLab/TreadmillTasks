import pyb, machine, time
import pyControl.hardware as _h


class LEDStim:
    "LED stimuli."
    def __init__(self):
        """PINS should be exactly `Ndirections` strings"""
        self.n_directions = 5
        pins = ('W45',    # Dir0
                'W43',    # Dir1
                'W24',    # Dir2
                'W10',    # Dir3
                'W68')    # Dir4
        powerlines = ('W16', 'W50', 'W60', 'W22')  # this variable indicates the POW pins used so that their logic level is inverted automatically.

        for d in range(self.n_directions):
            led = 'led' + str(d)
            setattr(self, led, _h.Digital_output(pin=pins[d], inverted=pins[d] in powerlines))
            getattr(self, led).off()

    def all_off(self):
        "turn off all LEDs"
        for d in range(self.n_directions):
            led = 'led' + str(d)
            getattr(self, led).off()

    def all_on(self):
        "turn on all LEDs"
        for d in range(self.n_directions):
            led = 'led' + str(d)
            getattr(self, led).on()

    def cue_led(self, direction:int):
        "turn on the LED corresponding to the given direction"
        for d in range(self.n_directions):
            led = 'led' + str(d)
            if d == direction:
                getattr(self, led).on()
            else:
                getattr(self, led).off()

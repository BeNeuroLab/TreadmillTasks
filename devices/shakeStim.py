import pyb, machine, time
import pyControl.hardware as _h


class shakeStim:
    "Earthequake machine stimuli."
    def __init__(self,port_exp):
        """PINS should be exactly `Ndirections` strings"""

        self.sol_0 = _h.Digital_output(pin=port_exp.port_6.DIO_A)
        # self.sol_1 = _h.Digital_output(pin=port_exp.port_6.DIO_B)
        self.sol_1 = _h.Digital_output(pin=port_exp.port_6.POW_A, inverted=True)
        self.sol_2 = _h.Digital_output(pin=port_exp.port_6.POW_B, inverted=True)
        self.sol_3 = _h.Digital_output(pin=port_exp.port_3.DIO_A)
        self.sol_4 = _h.Digital_output(pin=port_exp.port_3.DIO_B)
        self.sol_5 = _h.Digital_output(pin=port_exp.port_3.POW_A, inverted=True)
        self.sol_6 = _h.Digital_output(pin=port_exp.port_3.POW_B, inverted=True)

        self.sol_7 = _h.Digital_output(pin=port_exp.port_4.DIO_A)
        self.sol_8 = _h.Digital_output(pin=port_exp.port_4.DIO_B)
        self.sol_9 = _h.Digital_output(pin=port_exp.port_4.POW_A, inverted=True)
        self.sol_10 = _h.Digital_output(pin=port_exp.port_4.POW_B, inverted=True)

    def all_off(self):
        "turn off all sols"
        for d in range(self.n_directions):
            sol = 'sol_' + str(d)
            getattr(self, sol).off()

    def sol_on(self, direction: int):
        "turn on the sol corresponding to the given direction"
        sol = 'sol_' + str(direction)
        getattr(self, sol).on()

    def sol_off(self, direction: int):
        sol = 'sol_' + str(direction)
        getattr(self, sol).off()
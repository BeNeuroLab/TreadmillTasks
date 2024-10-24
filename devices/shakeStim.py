import pyb, machine, time
import pyControl.hardware as _h


class shakeStim:
    "Earthequake machine stimuli."
    def __init__(self,port_exp):
        """PINS should be exactly `Ndirections` strings"""
        self.n_directions = 1
        self.sol_0 = _h.Digital_output(pin=port_exp.port_8.DIO_A)
        self.sol_1 = _h.Digital_output(pin=port_exp.port_8.DIO_B)
        self.sol_2 = _h.Digital_output(pin=port_exp.port_8.POW_A, inverted=True)
        #self.sol_3 = _h.Digital_output(pin=port_exp.port_8.POW_B, inverted=True)
        # self.sol_1.off()

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
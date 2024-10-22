import pyb, machine, time
import pyControl.hardware as _h


class shakeStim:
    "Earthequake machine stimuli."
    def __init__(self,port_exp):
        """PINS should be exactly `Ndirections` strings"""
        self.n_directions = 1
        self.sol_1 = _h.Digital_output(pin=port_exp.port_5.DIO_B)
        self.sol_1.on()

import pyb, machine, time
import pyControl.hardware as _h


class shakeStim:
    "Earthequake machine stimuli."
    def __init__(self,port_exp):
        """PINS should be exactly `Ndirections` strings"""
        self.port_exp = port_exp
        self.n_directions = 6
        pins = (
            self.port_exp.port_8.POW_B,
        )
        
        powerlines = (port_exp.port_8.POW_B)  
        # this variable indicates the POW pins used so that their logic level is inverted automatically.

        for d in range(self.n_directions):
            sol = 'sol' + str(d)
            setattr(self, sol, _h.Digital_output(pin=pins[d], inverted=pins[d] in powerlines))
            #getattr(self, sol).off()
        

    def all_off(self):
        "turn off all sols"
        for d in range(self.n_directions):
            sol = 'sol' + str(d)
            getattr(self, sol).off()

    def all_on(self):
        "turn on all sols"
        for d in range(self.n_directions):
            sol = 'sol' + str(d)
            getattr(self, sol).on()

    def cue_sol(self, direction:int):
        "turn on the sol corresponding to the given direction"
        for d in range(self.n_directions):
            sol = 'sol' + str(d)
            if d == direction:
                getattr(self, sol).on()
            else:
                getattr(self, sol).off()

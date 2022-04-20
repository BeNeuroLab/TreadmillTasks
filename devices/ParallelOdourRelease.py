import pyb, machine, time
import pyControl.hardware as _h


class ParallelOdourRelease():
    # Odour system.
    def __init__(self):
        # PINS should be exactly Ndirections x NstimPerDir strings
        # specifying the pins! iterating over Direction and Odour, Odour ==0 is clean air
        self.Ndirections = 5
        self.NstimPerDir = 2
        pins = ('W16', 'W50',    # Dir1
                'W60', 'W22',    # Dir2
                'W45', 'W43',    # Dir3
                'W24', 'W10',    # Dir4
                'W68', 'W66')    # Dir5
        powerlines = ('W16', 'W50', 'W60', 'W22')  # this variable indicates the POW pins used so that their logic level is inverted automatically.

        counter = 0
        for dir in range(self.Ndirections):
            for stim in range(self.NstimPerDir):
                sol = self._sol_name(dir, stim)
                setattr(self, sol, _h.Digital_output(pin=pins[counter], inverted=pins[counter] in powerlines))
                getattr(self, sol).off()

                counter += 1

    def all_off(self):
        for dir in range(self.Ndirections):
            for stim in range(self.NstimPerDir):
                getattr(self, self._sol_name(dir, stim)).off()

    def clean_air_on(self):
        """
        clean air (Odour==0) on everywhere and odourant off.
        """
        for dir in range(self.Ndirections):
            getattr(self, self._sol_name(dir, 0)).on()
            getattr(self, self._sol_name(dir, 1)).off()

    def odour_release(self, dir: int):
        for direction in range(self.Ndirections):
            odour = 1 if direction == dir else 0
            getattr(self, self._sol_name(direction, odour)).on()
            getattr(self, self._sol_name(direction, 1 - odour)).off()

    @staticmethod
    def _sol_name(dir: int, odour: int) -> str:
        return 'Dir' + str(dir) + 'Odour' + str(odour)

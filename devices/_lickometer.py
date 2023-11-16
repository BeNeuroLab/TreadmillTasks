from pyControl.hardware import Digital_input, Digital_output

class Lickometer():
    # Two lick detectors and two solenoids.
    def __init__(self,  lick_port, sol_port, rising_event_A='lick_1', debounce=5, **kwargs):
        self.lick_1 = Digital_input(lick_port.DIO_A, rising_event_A, debounce)
        self.SOL_1  = Digital_output(sol_port.POW_B)
        self.SOL_2  = Digital_output(sol_port.POW_A)

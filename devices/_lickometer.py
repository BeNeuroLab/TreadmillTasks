from pyControl.hardware import Digital_input, Digital_output

class Lickometer():
    """
    Optical lickometer to detect lick events
    Device documentation on: https://sanworks.io/shop/viewproduct?productID=1020
    https://sanworks.io/forums/d/3931-optical-lickometer-questions/2
    
    Configuration:
    Red wire: positive; Purple wire: negative
    Wires closer to the 4mm nut: emitter; wires further from: transistor
    
    # All purple wires --> GND
    # Transistor positive end --> Digital input port
    # Emitter positive end --> 500 ohm resistor --> Power source
    # Add a 40k pull-up resistor between power source and digital input

    when nothing is in the beam path, the infrared light hits the phototransistor which becomes a low resistance path to ground,
    pulling the NI input line low (0V). When a tongue breaks the beam, the phototransistor goes back to high resistance, and the 15k pull-up resistor pulls the line high (5V).
    """
    
    def __init__(self,  lick_port, sol_port, rising_event_A='lick_1', debounce=5, **kwargs):
        # Event triggered when pin is pulled down
        self.lick_1 = Digital_input(lick_port.DIO_A, rising_event_A=None, falling_event=rising_event_A, debounce=debounce, pull='up')
        self.SOL_1  = Digital_output(sol_port.POW_A)

        self.SOL_1.off()

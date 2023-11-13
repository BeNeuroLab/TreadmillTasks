import utime
import pyControl.hardware as _h


class AudioStim(_h.Audio_player):
    "Audio stimuli from 7 speakers using PyControl's `Audio_player`"
    def __init__(self, port: _h.Port):
        """PINS should be exactly `Ndirections` strings"""
        super().__init__(port)
        self.set_enabled(self, left=True, right=False)  # only left channel is soldered to the speakers
        self.set_volume(25)  # Between 1 - 30
        utime.sleep_ms(20)  # wait for the audio player to be ready

        self.n_directions = 7
        pins = ('W10',    # Dir0
                'W68',    # Dir1
                'W66',    # Dir2
                'W58',    # Dir3
                'W14',    # Dir4
                'W64',    # Dir5
                'W62')    # Dir6
        #the POW pins used so that their logic level is inverted automatically.
        powerlines = ('W23', 'W25', 'W62', 'W64','W30','W32')

        for d in range(self.n_directions):
            spk = 'spk' + str(d)
            setattr(self, spk, _h.Digital_output(pin=pins[d], inverted=pins[d] in powerlines))
            getattr(self, spk).off()

        # Start playing the audio file
        self.play(folder_num = 1, file_num = 1)  # Play file 1 from folder 1.
        utime.sleep_ms(20)  # wait for the audio player to be ready

    def all_off(self):
        "turn off all Speakers"
        for d in range(self.n_directions):
            spk = 'spk' + str(d)
            getattr(self, spk).off()

    def all_on(self):
        "turn on all the Speakers"
        for d in range(self.n_directions):
            spk = 'spk' + str(d)
            getattr(self, spk).on()

    def cue(self, direction:int):
        "turn on the Speaker corresponding to the given direction"
        for d in range(self.n_directions):
            spk = 'spk' + str(d)
            if d == direction:
                getattr(self, spk).on()
            else:
                getattr(self, spk).off()

    def cue_array(self, arr:list):
        "turn on the all the speakers corresponding to the given directions in `arr`"
        self.all_off()
        for d in arr:
            spk = 'spk' + str(d)
            getattr(self, spk).on()

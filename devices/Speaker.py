"""
Custom class for the Speaker device for frequency feedback. 
"""

import pyControl.hardware as _h
from devices._audio_board import Audio_board


class Speaker(Audio_board):
    def __init__(self, port: _h.Port):
        """
        Initialize the Speaker device with the specified port.
        """
        super().__init__(port)
        self.off() # Ensure the speaker is off initially
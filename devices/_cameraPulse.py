import pyb, machine, time
import pyControl.hardware as _h

class CameraPulse(_h.Digital_output):
    "generate a clock to trigger the cameras"
    def __init__(self, pin, trigger_rate=100, duty_cycle=50):
        super().__init__(pin, pulse_enabled=True)
        self.duty_cycle = duty_cycle
        self.trigger_rate = trigger_rate

    def start(self):
        "start generating the trigger pulse, with an immediate rising edge"
        self.pulse(freq=self.trigger_rate, duty_cycle=self.duty_cycle)

    def stop(self):
        "stop generating the trigger pulse"
        self.off()

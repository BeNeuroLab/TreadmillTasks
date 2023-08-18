import machine
import pyControl.hardware as _h

class Reward(_h.IO_object):
    "Open the solnoid to release water reward"
    def __init__(self, sol:_h.Digital_output, reward_duration: int=100):
        "reward_duration in ms"
        self.reward_duration = int(reward_duration)
        self.sol = sol
        self.sol.off()
        self.timer = machine.Timer(_h.available_timers.pop())

    def release(self):
        "release water reward"
        self.sol.on()
        self.timer.init(period=self.reward_duration, mode=machine.Timer.ONE_SHOT, callback=self.callback)

    def _callback(self, timer):
        "start generating the trigger pulse"
        self.sol.off()
    
    def stop(self):
        "stop generating the trigger pulse"
        self.timer.deinit() # stop the timer
        self.sol.off()

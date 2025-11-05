import pyb
import pyControl.hardware as _h

class Reward(_h.IO_object):
    "Open the solnoid to release water reward"
    def __init__(self, sol:_h.Digital_output, sync:_h.Digital_output, reward_duration: int=100):
        """
        reward_duration in ms
        self.sync_to_reward is a digital output that goes high when reward is being delivered
                            copying reward state to sync with pyPhotometry    
        """
        self.timer = pyb.Timer(_h.available_timers.pop())
        self.reward_duration = reward_duration
        self.sync_to_reward  = _h.Digital_output(sync)
        self.sol = sol
        self.sol.off()
        self.sync_to_reward.off()
        self.sol_state = False  # to avoid turning on the solenoid twice
            
    @property
    def reward_duration(self):
        return 1000 / self.reward_freq
        
    @reward_duration.setter
    def reward_duration(self, new):
        self.timer.deinit()
        self.reward_freq = int(1000 / new)
        self.timer.init(freq=self.reward_freq, callback=None)
        
    def release(self):
        "release water reward"
        if self.sol_state is False:
            self.sol.on()
            self.sol_state = True
            self.sync_to_reward.on()
            self.timer.counter(0)
            self.timer.callback (self._callback)

    def _callback(self, timer):
        "turn off the sol"
        self.sol.off()
        self.sol_state = False
        self.sync_to_reward.off()
        self.timer.callback(None)
    
    def stop(self):
        "stop generating the trigger pulse"
        self.timer.deinit() # stop the timer
        self.sol.off()
        self.sol_state = False
        self.sync_to_reward.off()

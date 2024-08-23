import time, gc, math
from array import array
from machine import Pin, SPI
from pyControl.hardware import *
from PAA5100JE_firmware import PAA5100JE_firmware

def to_signed_16(value):
    """Convert a 16-bit integer to a signed 16-bit integer."""
    if value & 0x8000:  # Check if the sign bit is set
        value -= 0x10000  # Convert to negative
    return value

class PAA5100JE():
    """Optical tracking sensor."""
    def __init__(self, spi_port: str, 
                 spi_cs_gpio: str,
                 reset: str = None, 
                 sck: str = None, 
                 mosi: str =None, 
                 miso: str =None):
                     
        # Initialize SPI
        # SPI_type = 'SPI1' or 'SPI2' or 'softSPI'
        SPIparams = {'baudrate': 400000, 'polarity': 0, 'phase': 0,
                     'bits': 8, 'firstbit': machine.SPI.MSB}
        if '1' in spi_port:
            self.spi = SPI(1, **SPIparams)

        elif '2' in spi_port:
            self.spi = SPI(2, **SPIparams)

        elif 'soft' in spi_port.lower():  # Works for newer versions of micropython
            self.spi = SoftSPI(sck=Pin(sck, mode=machine.Pin.OUT, pull=machine.Pin.PULL_DOWN),
                                       mosi=Pin(mosi, mode=machine.Pin.OUT, pull=machine.Pin.PULL_DOWN),
                                       miso=Pin(miso, mode=machine.Pin.IN),
                                       **SPIparams
                                       )
            
        # Handle Chip Select (CS) pin
        self.select = Digital_output(pin=spi_cs_gpio, inverted=True)
        self.reset = Digital_output(pin=reset, inverted=True)
        self.select.off()  # Deselect the device by setting CS high
        self.reset.off()
        time.sleep_ms(50)

        # Reset the sensor
        self._write(REG_POWER_UP_RESET, 0x5A)
        time.sleep_ms(20)
        for offset in range(5):
            self._read(REG_DATA_READY + offset)
       
        # Initiate registers using firmware
        self.firmware = PAA5100JE_firmware()
        self.firmware.init_registers()
    
    def set_rotation(self, degrees:int =0):
        """Set orientation of PAA5100 in increments of 90 degrees."""
        if degrees == 0:
            self.set_orientation(invert_x=True, invert_y=True, swap_xy=True)
        elif degrees == 90:
            self.set_orientation(invert_x=False, invert_y=True, swap_xy=False)
        elif degrees == 180:
            self.set_orientation(invert_x=False, invert_y=False, swap_xy=True)
        elif degrees == 270:
            self.set_orientation(invert_x=True, invert_y=False, swap_xy=False)
        else:
            raise TypeError("Degrees must be one of 0, 90, 180 or 270")

    def set_orientation(self, invert_x:bool =True, invert_y:bool =True, swap_xy:bool =True):
        """Set orientation of PAA5100 manually."""
        value = 0
        if swap_xy:
            value |= 0b10000000
        if invert_y:
            value |= 0b01000000
        if invert_x:
            value |= 0b00100000
        self._write(REG_ORIENTATION, value)
    
    def _write(self, register: bytes, value: bytes):
        """Write into register"""
        self.select.on()
        self.spi.write(bytearray([register | 0x80, value]))
        self.select.off()
    
    def _read(self, register: bytes, length: int =1):
        """Read register"""
        # Create a buffer to send (with one extra byte for the register)
        send_buf = bytearray([register]) + bytearray(length)
        # Create a result buffer of the same length as the send_buf
        result = bytearray(len(send_buf))
        
        self.select.on()
        self.spi.write_readinto(send_buf, result)
        self.select.off()
        
        # Return the read result, skipping the first byte (which corresponds to the register)
        return result[1:] if length > 1 else result[1]

    def _bulk_write(self, data: bytearray):
        """Write a list of commands into registers"""
        for x in range(0, len(data), 2):
            register, value = data[x : x + 2]
            self._write(register, value)
                
    def read_registers(self, reg: bytes, buf: bytearray, len: int):
        """Read an array of data from the registers"""
        self.select.on()
        self.spi.write(bytearray([reg]))
        # Read data from the register
        buf[:] = self.spi.read(len)
        self.select.off()   

    def shut_down(self, deinitSPI:bool =True):
        """Shutdown the sensor"""
        self.select.off()
        time.sleep_ms(1)
        self.select.on()
        time.sleep_ms(1)
        self.reset.on()
        time.sleep_ms(60)
        self.write(REG_SHUTDOWN, 1)
        time.sleep_ms(1)
        self.select.off()
        time.sleep_ms(1)
        if deinitSPI:
            self.SPI.deinit()
        
class MotionDetector(Analog_input):
    """
    Using the Analog_input code to interface with 2 PAA5100JE sensors
    reading `x` (SPI2) and `y` (softSPI) separately.
    """
    def __init__(self, reset: str, cs1: str, cs2: str,
                 name='MotDet', threshold=1, calib_coef=1,
                 sampling_rate=100, event='motion'):
        
        # Create SPI objects
        self.motSen_x = PAA5100JE('SPI2', reset, cs1)
        self.motSen_y = PAA5100JE('SPI2', reset, cs2)

        self._threshold = threshold
        self.calib_coef = calib_coef
        
        # Motion sensor variables
        self.x_buffer = bytearray(12)
        self.y_buffer = bytearray(12)
        self.x_buffer_mv = memoryview(self.x_buffer)
        self.y_buffer_mv = memoryview(self.y_buffer)
        
        self.delta_x, self.delta_y = 0, 0    # accumulated position
        self._delta_x, self._delta_y = 0, 0  # instantaneous position
        self.x, self.y = 0, 0  # to be accessed from the task, unit=mm
        
        # Parent
        Analog_input.__init__(self, pin=None, name=name + '-X', sampling_rate=int(sampling_rate),
                              threshold=threshold, rising_event=event, falling_event=None,
                              data_type='l')
        self.data_chx = self.data_channel
        self.data_chy = Data_channel(name + '-Y', sampling_rate, data_type='l')
        self.crossing_direction = True  # to conform to the Analog_input syntax
        self.timestamp = fw.current_time
        self.acquiring = False
        
        gc.collect()
        time.sleep_ms(2)
    
    @property
    def threshold(self):
        """return the value in mms"""
        return math.sqrt(int(self._threshold**2) * self.calib_coef)
    
    def reset_delta(self):
        """reset the accumulated position data"""
        self.delta_x, self.delta_y = 0, 0
    
    def read_sample(self):
        """read motion once"""
        # All units are in millimeters
        # Read motion in x direction
        self.motSen_x.read_registers(REG_MOTION_BURST, self.x_buffer_mv, 12)
        self._delta_x = to_signed_16((self.x_buffer_mv[3] << 8) | self.x_buffer_mv[2])

        # Read motion in y direction
        self.motSen_y.read_registers(REG_MOTION_BURST, self.y_buffer_mv, 12)
        self._delta_y = to_signed_16((self.y_buffer_mv[5] << 8) | self.y_buffer_mv[4])

        # Record accumulated motion
        self.delta_y += self._delta_y
        self.delta_x += self._delta_x        
        
        if self.delta_x**2 + self.delta_y**2 >= self._threshold:
            print(f"x coordinate: {self._delta_x:>10.5f} | y coordinate: {self._delta_y:>10.5f}")
    
    def _timer_ISR(self, t):
        """Read a sample to the buffer, update write index."""
        self.read_sample()
        self.data_chx.put(self._delta_x)
        self.data_chy.put(self._delta_y)

        if self.delta_x**2 + self.delta_y**2 >= self._threshold:
            self.x = self.delta_x
            self.y = self.delta_y
            self.reset_delta()
            self.timestamp = fw.current_time
            interrupt_queue.put(self.ID) 

    def _stop_acquisition(self):
        """Stop sampling analog input values."""
        self.timer.deinit()
        self.data_chx.stop()
        self.data_chy.stop()
        self.motSen_x.shut_down(deinitSPI=False)      
        self.motSen_y.shut_down()
        self.acquiring = False
        self.reset_delta()
        
    def _start_acquisition(self):
        """Start sampling analog input values"""
        self.timer.init(freq=self.data_chx.sampling_rate)
        self.timer.callback(self._timer_ISR)
        self.acquiring = True

    def record(self):
        """Start streaming data to computer."""
        self.data_chx.record()
        self.data_chy.record()
        if not self.acquiring:
            self._start_acquisition()

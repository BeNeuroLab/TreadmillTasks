import time, gc, math
from array import array
from machine import Pin, SPI
from pyControl.hardware import *

def to_signed_16(value):
    """Convert a 16-bit integer to a signed 16-bit integer."""
    if value & 0x8000:  # Check if the sign bit is set
        value -= 0x10000  # Convert to negative
    return value

WAIT = -1
# PAA5100 register definitions
REG_ID = 0x00
REG_DATA_READY = 0x02
REG_MOTION_BURST = 0x16
REG_POWER_UP_RESET = 0x3A
REG_ORIENTATION = 0x5B
REG_RESOLUTION = 0x4E

REG_RAWDATA_GRAB = 0x58
REG_RAWDATA_GRAB_STATUS = 0x59

class PAA5100JE():
    def __init__(self, spi_port=None, reset=None, spi_cs_gpio=None, sck=0, mosi=0, miso=0):
        # Initialize SPI
        # SPI_type = 'SPI1' or 'SPI2' or 'softSPI'
        SPIparams = {'baudrate': 400000, 'polarity': 0, 'phase': 0,
                     'bits': 8, 'firstbit': machine.SPI.MSB}
        if '0' in spi_port:
            self.spi = SPI(0, **SPIparams)

        elif '1' in spi_port:
            self.spi = SPI(1, **SPIparams)

        elif 'soft' in spi_port.lower():  # Works for newer versions of micropython
            self.spi = SoftSPI(sck=Pin(sck, mode=machine.Pin.OUT, pull=machine.Pin.PULL_DOWN),
                                       mosi=Pin(mosi, mode=machine.Pin.OUT, pull=machine.Pin.PULL_DOWN),
                                       miso=Pin(miso, mode=machine.Pin.IN),
                                       **SPIparams
                                       )
            
        # Handle Chip Select (CS) pin
        if spi_cs_gpio is not None:
            self.select = Digital_output(pin=spi_cs_gpio, inverted=True)
            self.reset = Digital_output(pin=reset, inverted=True)
            self.select.off()  # Deselect the device by setting CS high
            self.reset.off()
            time.sleep(0.05)

        # Reset the sensor
        self._write(REG_POWER_UP_RESET, 0x5A)
        time.sleep(0.02)
        for offset in range(5):
            self._read(REG_DATA_READY + offset)

        self.init_registers()

        # Validate device ID and revision
        product_id = self.get_id()
        if product_id != 0x49:
            raise RuntimeError(f"Invalid Product ID or Revision for PAA5100: 0x{product_id:02x}")

    def get_id(self):
        """Get chip ID and revision from PAA5100."""
        return self._read(REG_ID, 1)
    
    def set_rotation(self, degrees=0):
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

    def set_orientation(self, invert_x=True, invert_y=True, swap_xy=True):
        """Set orientation of PAA5100 manually."""
        value = 0
        if swap_xy:
            value |= 0b10000000
        if invert_y:
            value |= 0b01000000
        if invert_x:
            value |= 0b00100000
        self._write(REG_ORIENTATION, value)
    
    def get_motion(self):
        buf = bytearray(12)
        self.read_registers(REG_MOTION_BURST, buf, 12)
        dr = buf[0]
        x_out = to_signed_16((buf[3] << 8) | buf[2])
        y_out = to_signed_16((buf[5] << 8) | buf[4])
        quality = buf[6]
        shutter_upper = buf[10]
        if (dr & 0b10000000) and not ((quality < 0x19) and (shutter_upper == 0x1f)):
            return x_out, y_out
        else:
            x_out, y_out = 0, 0
        time.sleep_ms(1)

        return x_out, y_out
    
    def _write(self, register, value):
        if self._spi_cs_gpio:
            self.select.on()
        self.spi.write(bytearray([register | 0x80, value]))
        if self._spi_cs_gpio:
            self.select.off()
    
    def _read(self, register, length=1):
        # Create a buffer to send (with one extra byte for the register)
        send_buf = bytearray([register]) + bytearray(length)
        # Create a result buffer of the same length as the send_buf
        result = bytearray(len(send_buf))
        
        if self._spi_cs_gpio:
            self.select.on()
        self.spi.write_readinto(send_buf, result)
        if self._spi_cs_gpio:
            self.select.off()
        
        # Return the read result, skipping the first byte (which corresponds to the register)
        return result[1:] if length > 1 else result[1]

    def _bulk_write(self, data):
        for x in range(0, len(data), 2):
            register, value = data[x : x + 2]
            if register == WAIT:
                time.sleep(value / 1000)
            else:
                self._write(register, value)
                
    def read_registers(self, reg, buf, len):
        self.select.on()
        self.spi.write(bytearray([reg]))
        # Read data from the register
        buf[:] = self.spi.read(len)
        self.select.off()   
        
    def init_registers(self):
        self._bulk_write([
            0x7F, 0x00,
            0x55, 0x01,
            0x50, 0x07,

            0x7F, 0x0E,
            0x43, 0x10
        ])
        if self._read(0x67) & 0b10000000:
            self._write(0x48, 0x04)
        else:
            self._write(0x48, 0x02)
        self._bulk_write([
            0x7F, 0x00,
            0x51, 0x7B,
            0x50, 0x00,
            0x55, 0x00,
            0x7F, 0x0E
        ])
        if self._read(0x73) == 0x00:
            c1 = self._read(0x70)
            c2 = self._read(0x71)
            if c1 <= 28:
                c1 += 14
            if c1 > 28:
                c1 += 11
            c1 = max(0, min(0x3F, c1))
            c2 = (c2 * 45) // 100
            self._bulk_write([
                0x7F, 0x00,
                0x61, 0xAD,
                0x51, 0x70,
                0x7F, 0x0E
            ])
            self._write(0x70, c1)
            self._write(0x71, c2)
        self._bulk_write([
            0x7F, 0x00,
            0x61, 0xAD,

            0x7F, 0x03,
            0x40, 0x00,

            0x7F, 0x05,
            0x41, 0xB3,
            0x43, 0xF1,
            0x45, 0x14,

            0x5F, 0x34,
            0x7B, 0x08,
            0x5E, 0x34,
            0x5B, 0x11,
            0x6D, 0x11,
            0x45, 0x17,
            0x70, 0xE5,
            0x71, 0xE5,

            0x7F, 0x06,
            0x44, 0x1B,
            0x40, 0xBF,
            0x4E, 0x3F,

            0x7F, 0x08,
            0x66, 0x44,
            0x65, 0x20,
            0x6A, 0x3A,
            0x61, 0x05,
            0x62, 0x05,

            0x7F, 0x09,
            0x4F, 0xAF,
            0x5F, 0x40,
            0x48, 0x80,
            0x49, 0x80,
            0x57, 0x77,
            0x60, 0x78,
            0x61, 0x78,
            0x62, 0x08,
            0x63, 0x50,

            0x7F, 0x0A,
            0x45, 0x60,

            0x7F, 0x00,
            0x4D, 0x11,
            0x55, 0x80,
            0x74, 0x21,
            0x75, 0x1F,
            0x4A, 0x78,
            0x4B, 0x78,
            0x44, 0x08,

            0x45, 0x50,
            0x64, 0xFF,
            0x65, 0x1F,

            0x7F, 0x14,
            0x65, 0x67,
            0x66, 0x08,
            0x63, 0x70,
            0x6F, 0x1C,

            0x7F, 0x15,
            0x48, 0x48,

            0x7F, 0x07,
            0x41, 0x0D,
            0x43, 0x14,
            0x4B, 0x0E,
            0x45, 0x0F,
            0x44, 0x42,
            0x4C, 0x80,

            0x7F, 0x10,
            0x5B, 0x02,

            0x7F, 0x07,
            0x40, 0x41,

            WAIT, 0x0A,  # Wait 10ms

            0x7F, 0x00,
            0x32, 0x00,

            0x7F, 0x07,
            0x40, 0x40,

            0x7F, 0x06,
            0x68, 0xF0,
            0x69, 0x00,

            0x7F, 0x0D,
            0x48, 0xC0,
            0x6F, 0xD5,

            0x7F, 0x00,
            0x5B, 0xA0,
            0x4E, 0xA8,
            0x5A, 0x90,
            0x40, 0x80,
            0x73, 0x1F,

            WAIT, 0x0A,  # Wait 10ms

            0x73, 0x00
        ])
        
class MotionDetector(Analog_input):
    def __init__(self, reset, cs1, cs2,
                 name='MotDet', threshold=1, calib_coef=1,
                 sampling_rate=100, event='motion'):
        
        # Create SPI objects
        ## Change to same SPI, sck, miso, and mosi
        self.motSen_x = PAA5100JE('SPI0', reset, cs1, 18, 19, 16)
        self.motSen_y = PAA5100JE('SPI1', reset, cs2, 10, 11, 12)

        self._threshold = threshold
        self.calib_coef = calib_coef
        
        # Motion sensor variables
        self.x_buffer = array('i', [0, 0])
        self.y_buffer = array('i', [0, 0])
        self.x_buffer_mv = memoryview(self.x_buffer)
        self.y_buffer_mv = memoryview(self.y_buffer)
        
        self.prev_x = 0
        self.prev_y = 0
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
        "return the value in cms"
        return math.sqrt(int(self._threshold**2) * self.calib_coef)
    
    def reset_delta(self):
        # reset the accumulated position data
        self.delta_x, self.delta_y = 0, 0
    
    def read_sample(self):
        # Units are in millimeters
        current_motion_x = self.motSen_x.get_motion()
        current_motion_y = self.motSen_y.get_motion()
        
        if current_motion_x is not None and current_motion_y is not None:
            self.x_buffer_mv = current_motion_x
            self.y_buffer_mv = current_motion_y

            self.delta_x = self.x_buffer_mv[0]
            self.delta_y = self.y_buffer_mv[1]

            self._delta_x = self.delta_x - self.prev_x
            self._delta_y = self.delta_y - self.prev_y
            
            # Update previous coordinates
            self.prev_x = self.delta_x
            self.prev_y = self.delta_y
        
        disp = self.displacement()
        
        if self.delta_x**2 + self.delta_y**2 >= self._threshold:
            print(f"x coordinate: {self.delta_x:>10.5f} | y coordinate: {self.delta_y:>10.5f} | Displacement: {disp:>12.5f}")
                
    def displacement(self):
        # Calculate displacement using the change of coordinates with time
        disp = math.sqrt(self._delta_x**2 + self._delta_y**2)
        return disp
    
    def _timer_ISR(self, t):
        "Read a sample to the buffer, update write index."
        self.read_sample()
        self.data_chx.put(self._delta_x)
        self.data_chy.put(self._delta_y)

        if self.delta_x**2 + self.delta_y**2 >= self._threshold:
            self.x = self.delta_x
            self.y = self.delta_y
            self.reset_delta()
            self.timestamp = fw.current_time

    def _stop_acquisition(self):
        # Stop sampling analog input values.
        self.timer.deinit()
        self.data_chx.stop()
        self.data_chy.stop()
        self.motSen_x.shut_down(deinitSPI=False)      
        self.motSen_y.shut_down()
        self.acquiring = False
        self.reset_delta()
        
    def _start_acquisition(self):
        # Start sampling analog input values.
        self.timer.init(freq=self.data_chx.sampling_rate)
        self.timer.callback(self._timer_ISR)
        self.acquiring = True

    def record(self):
        "Start streaming data to computer."
        self.data_chx.record()
        self.data_chy.record()
        if not self.acquiring:
            self._start_acquisition()

# --------------------------------------------------------
if __name__ == "__main__":    
    motion_sensor = MotionDetector(2, 17, 13)
    try:
        while True:
            try:
                motion_sensor.read_sample()
            except RuntimeError:
                continue
    except KeyboardInterrupt:
        pass

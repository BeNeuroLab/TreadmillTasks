import time
import gc
import math
import machine

from pyControl.hardware import *
import devices.PAA5100JE_firmware as PAA5100JE_firmware


def twos_comp(val, bits=16):
    """compute the 2's complement of int value val"""
    if (val & (1 << (bits - 1))) != 0:  # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)         # compute negative value
    return val                          # return positive value as is


class PAA5100JE():
    """
    Optical optical flow sensor:
    C++ code reference can be found on: https://github.com/pimoroni/pimoroni-pico.git
    and on https://github.com/zic-95/PAA5100JE/blob/main/src/PAA5100JE.cpp
    """
    def __init__(self, 
                SPI_type: str, 
                CS: str, 
                MI: str = None, 
                MO: str = None, 
                SCK: str = None
                ):

        # Initialize SPI
        # SPI_type = 'SPI1' or 'SPI2' or 'softSPI'
        SPIparams = {'baudrate': 2000000, 'polarity': 1, 'phase': 1,
                    'bits': 8, 'firstbit': machine.SPI.MSB}

        if '1' in SPI_type:
            self.spi = machine.SPI(1, **SPIparams)

        elif '2' in SPI_type:
            self.spi = machine.SPI(2, **SPIparams)

        elif 'soft' in SPI_type.lower():  # Works for newer versions of micropython
            self.spi = machine.SoftSPI(sck=machine.Pin(SCK, mode=machine.Pin.OUT, pull=machine.Pin.PULL_DOWN),
                                    mosi=machine.Pin(MO, mode=machine.Pin.OUT, pull=machine.Pin.PULL_DOWN),
                                    miso=machine.Pin(MI, mode=machine.Pin.IN),
                                    **SPIparams
                                    )

        # Define Chip Select (CS) pin (active low)
        self.select = Digital_output(pin=CS, inverted=True)

        time.sleep_ms(1)
        self.select.off() # Deselect the device by setting CS high
        time.sleep_ms(1)
        self.select.on() # Select the device by setting CS low
        time.sleep_ms(50)
        self.select.off()
        time.sleep_ms(1)

        self.power_up()  # Power up the sensor

        # Check for successful initialization
        prod_ID = self._read(0x00)
        prod_rev  = self._read(0x01)
        assert prod_ID == 0x49, "Bad init. Prod_ID={:#x}, Rev={:#x}, SPI={}".format(prod_ID, prod_rev, self.spi)

        # CPI from: https://github.com/zic-95/PAA5100JE/blob/1644a74095bf5f9345d43fffa26aea2661e1c56c/src/PAA5100JE.cpp#L75
        # distance from sensor fixed at 2cm=0.02m
        HEIGHT = 0.02 # m
        self.CPI = 11.914 * (1 / (HEIGHT))  # PixArt formulae

        burst_address = PAA5100JE_firmware.REG_MOTION_BURST
        burst_address &= ~0x80  # Flip MSB to 1
        self.burst_address = burst_address.to_bytes(1, 'little')

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
        self._write(PAA5100JE_firmware.REG_ORIENTATION, value)
    
    def _write(self, address: int, value: int):
        """Write value into register"""
        address |= 0x80  # Flip MSB to 1
        address = address.to_bytes(1, 'little')  # Convert the address from integer to a single byte
        value = value.to_bytes(1, 'little')    # Convert the value from integer to a single byte
        
        self.select.on()
        time.sleep_us(1)
        self.spi.write(address)   # find specific address of the device
        self.spi.write(value)     # write value into the above address of the device
        time.sleep_us(5)          # tSCLK-NCS for write operation
        self.select.off()
        time.sleep_us(5)          # tSWW/tSWR (=120us) minus tSCLK-NCS.

    def _read(self, address: int):
        """Read register"""
        # Create a buffer to send
        address &= ~0x80  # Ensure MSB is 0
        address = address.to_bytes(1, 'little')  # Convert the integer to a single byte
        
        self.select.on()
        time.sleep_us(1)
        self.spi.write(address)
        time.sleep_us(5)  # tSRAD

        data = self.spi.read(1)

        val = int.from_bytes(data, 'little')  # converts received data back to integer for further calculations
        time.sleep_us(1)  # tSCLK-NCS for read operation is 120ns
        self.select.off()
        time.sleep_us(5)  # tSRW/tSRR (=20us) minus tSCLK-NCS
        return val

    def _bulk_write(self, data: list[int]):
        """Write a list of commands into registers"""
        for x in range(0, len(data), 2):
            address, value = data[x : x + 2]
            self._write(address, value)

    def read_burst(self, buf: bytearray | memoryview):
        """Read an array of data from the registers, used for reading motion burst"""       
        self.select.on()
        time.sleep_us(1)
        self.spi.write(self.burst_address)
        time.sleep_us(5)
        # Read 12 bytes of data from the motion burst register
        self.spi.readinto(buf)
        time.sleep_us(5)
        self.select.off()
        time.sleep_us(50)

    def power_up(self):
        """
        Perform the power up sequenceL `_secret_sauce`
        """
        # Reset the sensor
        self._write(PAA5100JE_firmware.REG_POWER_UP_RESET, 0x5A)
        time.sleep_ms(1)

        # Read motion registers once after reset
        for offset in range(5):
            self._read(PAA5100JE_firmware.REG_DATA_READY + offset)

        # Registers initialization protocol
        PROGMEM = PAA5100JE_firmware.PROGMEM
        self._bulk_write(PROGMEM[0:10])

        if self._read(0x67) & 0b10000000:
            self._write(0x48, 0x04)
        else:
            self._write(0x48, 0x02)
        self._bulk_write(PROGMEM[10:20])

        if self._read(0x73) == 0x00:
            c1 = int(self._read(0x70))
            c2 = int(self._read(0x71))
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

        self._bulk_write(PROGMEM[20:154])
        time.sleep_ms(10)
        self._bulk_write(PROGMEM[154:186])
        time.sleep_ms(10)
        self._bulk_write(PROGMEM[186:])
        time.sleep_ms(10)


    def shut_down(self, deinitSPI:bool =True):
        """Shutdown the sensor"""
        self.select.off()
        time.sleep_ms(1)
        self.select.on()
        time.sleep_ms(60)
        self._write(PAA5100JE_firmware.REG_SHUTDOWN, 0xB6)
        time.sleep_ms(1)
        self.select.off()
        time.sleep_ms(1)
        if deinitSPI:
            self.spi.deinit()


class MotionDetector2(Analog_input):
    """
    Using the Analog_input code to interface with 2 PAA5100JE sensors
    reading `x` (SPI2) and `y` (SPI2) separately.
    """
    def __init__(self, reset: str, cs1: str, cs2: str,
                name='MotSen', threshold=1, calib_coef=1,  
                sampling_rate=100, event='motion'
                ):

        # Create SPI objects
        self.sensor_x = PAA5100JE('SPI2', cs1)
        self.sensor_y = PAA5100JE('SPI2', cs2)

        self.calib_coef = calib_coef
        self.threshold = threshold
        
        # Motion sensor variables
        self.x_buffer = bytearray(12)
        self.y_buffer = bytearray(12)
        self.x_buffer_mv = memoryview(self.x_buffer)
        self.y_buffer_mv = memoryview(self.y_buffer)
        self.delta_x_mv = self.x_buffer_mv[2:4]
        self.delta_y_mv = self.y_buffer_mv[4:6]

        self.delta_x, self.delta_y = 0, 0    # accumulated position
        self._delta_x, self._delta_y = 0, 0  # instantaneous position
        self.x, self.y = 0, 0  # to be accessed from the task, unit=mm

        # Parent
        Analog_input.__init__(self, pin=None, name=name + '-X', sampling_rate=int(sampling_rate),
                            threshold=threshold, rising_event=event, falling_event=None,
                            data_type='l'
                            )
        self.data_chx = self.data_channel
        self.data_chy = Data_channel(name + '-Y', sampling_rate, data_type='l')
        self.crossing_direction = True  # to conform to the Analog_input syntax
        self.timestamp = fw.current_time
        self.acquiring = False

        gc.collect()
        time.sleep_ms(2)

    @property
    def threshold(self):
        "return the value in mms"
        return math.sqrt(self._threshold)

    @threshold.setter
    def threshold(self, new_threshold):
        self._threshold = int((new_threshold / 2.54 * self.sensor_x.CPI)**2) * self.calib_coef
        self.reset_delta()

    def reset_delta(self):
        """reset the accumulated position data"""
        self.delta_x, self.delta_y = 0, 0

    def read_sample(self):
        """read motion in the interrupt routine"""
        # Read motion in x direction
        self.sensor_x.read_burst(self.x_buffer_mv)
        self._delta_x = twos_comp(int.from_bytes(self.delta_x_mv, 'little'))

        # Read motion in y direction
        self.sensor_y.read_burst(self.y_buffer_mv)
        self._delta_y = twos_comp(int.from_bytes(self.delta_y_mv, 'little'))
        
        # Record accumulated motion
        self.delta_y += self._delta_y
        self.delta_x += self._delta_x
        
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
        self.sensor_x.shut_down(deinitSPI=False)      
        self.sensor_y.shut_down()
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

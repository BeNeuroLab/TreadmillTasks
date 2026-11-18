import time
import gc
import math
import machine
import pyb
from array import array

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
                CS: str = None,
                MI: str = None,
                MO: str = None,
                SCK: str = None,
                select: Digital_output = None,
                initialise: bool = True
                ):

        # Initialize SPI
        # SPI_type = 'SPI1' or 'SPI2' or 'softSPI'
        SPIparams = {'baudrate': 1000000, 'polarity': 1, 'phase': 1,
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
        if select is None:
            self.select = Digital_output(pin=CS, inverted=True)
        else:
            self.select = select
        self.select.off()  # Deselect the device by setting CS high.

        # CPI from: https://github.com/zic-95/PAA5100JE/blob/1644a74095bf5f9345d43fffa26aea2661e1c56c/src/PAA5100JE.cpp#L75
        # distance from sensor fixed at 2cm=0.02m
        HEIGHT = 0.02 # m
        self.CPI = 11.914 * (1 / (HEIGHT))  # PixArt formulae

        burst_address = PAA5100JE_firmware.REG_MOTION_BURST
        burst_address &= ~0x80  # Flip MSB to 1
        self.burst_address = burst_address.to_bytes(1, 'little')
        self.initialised = False
        self.product_id = None
        self.revision = None

        if initialise:
            self.initialise()

    def initialise(self):
        self.initialised = False
        try:
            time.sleep_ms(1)
            self.select.off()
            time.sleep_ms(1)
            self.select.on()
            time.sleep_ms(50)
            self.select.off()
            time.sleep_ms(1)
            self.power_up()
            self.product_id = self._read(0x00)
            self.revision = self._read(0x01)
            # Both revisions are accepted by the Pimoroni PAA5100 driver.
            # This check establishes communication, not optical tracking health.
            if self.product_id != 0x49 or self.revision not in (0x00, 0x01):
                raise RuntimeError("Bad sensor identity: ID={:#x}, revision={:#x}".format(
                    self.product_id, self.revision))
            self.initialised = True
        finally:
            self.select.off()

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

    def set_orientation(self, invert_x:bool =False, invert_y:bool =False, swap_xy:bool =False):
        """Set orientation of PAA5100 manually."""
        value = 0
        if swap_xy:
            value |= 0b10000000
        if invert_y:
            value |= 0b01000000
        if invert_x:
            value |= 0b00100000
        self._write(PAA5100JE_firmware.REG_ORIENTATION, value)
        actual = self._read(PAA5100JE_firmware.REG_ORIENTATION) & 0xE0
        if actual != value:
            raise RuntimeError("Orientation readback failed: expected {:#x}, got {:#x}".format(
                value, actual))
    
    def _write(self, address: int, value: int):
        """Write value into register"""
        address |= 0x80  # Flip MSB to 1
        address = address.to_bytes(1, 'little')  # Convert the address from integer to a single byte
        value = value.to_bytes(1, 'little')    # Convert the value from integer to a single byte
        
        self.select.on()
        try:
            time.sleep_us(1)
            self.spi.write(address)
            self.spi.write(value)
            time.sleep_us(10)     # tSCLK-NCS
        finally:
            self.select.off()
            time.sleep_us(120)    # tSWW/tSWR guard before next access

    def _read(self, address: int):
        """Read register"""
        # Create a buffer to send
        address &= ~0x80  # Ensure MSB is 0
        address = address.to_bytes(1, 'little')  # Convert the integer to a single byte
        
        self.select.on()
        try:
            time.sleep_us(1)
            self.spi.write(address)
            time.sleep_us(20)  # tSRAD guard time before data valid
            data = self.spi.read(1)
            time.sleep_us(2)
            return int.from_bytes(data, 'little')
        finally:
            self.select.off()
            time.sleep_us(20)  # tSRW/tSRR guard before next access

    def _bulk_write(self, data: list[int]):
        """Write a list of commands into registers"""
        for x in range(0, len(data), 2):
            address, value = data[x : x + 2]
            self._write(address, value)

    def read_burst(self, buf: bytearray | memoryview):
        """Read an array of data from the registers, used for reading motion burst"""       
        self.select.on()
        try:
            time.sleep_us(5)
            self.spi.write(self.burst_address)
            time.sleep_us(20)  # allow data to be prepared
            self.spi.readinto(buf)
            time.sleep_us(10)
        finally:
            self.select.off()
            time.sleep_us(50)

    def power_up(self):
        """
        Perform the power up sequenceL `_secret_sauce`
        """
        # A previous interrupted configuration may have left another bank
        # selected, including when NRESET is not wired on the breakout.
        self._write(0x7F, 0x00)
        # Reset the sensor from the base register bank.
        self._write(PAA5100JE_firmware.REG_POWER_UP_RESET, 0x5A)
        time.sleep_ms(60)

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
        time.sleep_ms(20)


    def shut_down(self, deinitSPI:bool =True):
        """Shutdown the sensor"""
        try:
            self.select.off()
            time.sleep_ms(1)
            self.select.on()
            time.sleep_ms(60)
            self._write(PAA5100JE_firmware.REG_SHUTDOWN, 0xB6)
            time.sleep_ms(1)
        finally:
            self.select.off()
            self.initialised = False
            if deinitSPI:
                self.spi.deinit()


class MotionDetector(Analog_input):
    """
    Using the Analog_input code to interface with 2 PAA5100JE sensors
    reading `x` (SPI2) and `y` (SPI2) separately.
    """
    def __init__(self, reset: str, cs1: str, cs2: str,
                name='MotSen', threshold=1, calib_coef=1,  
                sampling_rate=100, event='motion'
                ):

        self.reset = Digital_output(pin=reset, inverted=True) if reset else None
        self.cs_x = Digital_output(pin=cs2, inverted=True)
        self.cs_y = Digital_output(pin=cs1, inverted=True)
        self.spi_type = 'SPI2'
        self.sensor_x = None
        self.sensor_y = None
        self._sensors_ready = False
        self.init_attempts = 0
        self.acquisition_fault = 0
        self.fault_axis = 0
        self._reading_axis = 0
        self.diagnostic_capacity = 0
        self.diagnostic_count = 0
        self._diagnostic_active = False
        self.calib_coef = calib_coef
        self._threshold_input = threshold
        self._threshold = int(threshold)
        self._deactivate_lines()
        
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

        # Optional continuous X-motion interface.  This is kept separate from
        # delta_x/delta_y because those values are reset whenever a thresholded
        # motion event is generated.
        self.continuous_motion_enabled = False
        self.continuous_window_ms = 0
        self.continuous_window_samples = 0
        self.x_positive_total = 0
        self.x_negative_total = 0
        self.x_window_abs_total = 0
        self.x_window_sample_count = 0
        self._x_window = []
        self._x_window_index = 0
        self.continuous_y_enabled = False
        self.y_window_abs_total = 0
        self._y_window = []

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
        self._threshold_input = new_threshold
        self._update_threshold()
        self.reset_delta()

    def _deactivate_lines(self):
        self.cs_x.off()
        self.cs_y.off()
        if self.reset:
            self.reset.off()

    def _pulse_reset(self):
        self._deactivate_lines()
        time.sleep_ms(1)
        if self.reset:
            self.reset.on()
            time.sleep_ms(5)
            self.cs_x.off()
            self.cs_y.off()
            self.reset.off()
        time.sleep_ms(50)

    def _update_threshold(self):
        if self.sensor_x:
            self._threshold = int((self._threshold_input / 2.54 * self.sensor_x.CPI) ** 2) * self.calib_coef

    def _make_sensor(self, select):
        return PAA5100JE(self.spi_type, select=select, initialise=False)

    def _initialise_sensor(self, axis_name, sensor):
        try:
            sensor.initialise()
        except Exception as error:
            raise AssertionError("{} sensor init failed: {}".format(axis_name, error))

    def _initialise_sensors(self):
        """Prepare the complete pair; a failed attempt never leaves one active."""
        assert not self.acquiring, 'Cannot initialise while acquiring'
        self.timer.deinit()
        self._sensors_ready = False
        for attempt in range(1, 4):
            self.init_attempts = attempt
            try:
                self._pulse_reset()
                self.sensor_x = self._make_sensor(self.cs_x)
                self.sensor_y = self._make_sensor(self.cs_y)
                self._initialise_sensor('X', self.sensor_x)
                time.sleep_ms(5)
                self._initialise_sensor('Y', self.sensor_y)
                self.sensor_x.set_orientation(invert_x=True)
                self.sensor_y.set_orientation(invert_y=True)
                self._update_threshold()
                self.reset_delta()
                self.x, self.y = 0, 0
                self._sensors_ready = True
                return
            except Exception:
                self._deactivate_lines()
                sensor = self.sensor_y or self.sensor_x
                if sensor:
                    try:
                        sensor.spi.deinit()
                    except Exception:
                        pass
                self.sensor_x = None
                self.sensor_y = None
                if attempt == 3:
                    raise

    def _run_start(self):
        # Hardware run_start precedes the framework clock and task run_start.
        # Prepare tasks without a motion event too, but leave their timer off
        # so they can configure continuous windows before calling record().
        self.acquisition_fault = 0
        self.fault_axis = 0
        self._initialise_sensors()
        if self.threshold_active:
            self._start_acquisition()

    def _run_stop(self):
        self._stop_acquisition()

    def reset_delta(self):
        """reset the accumulated position data"""
        self.delta_x, self.delta_y = 0, 0

    def configure_continuous_motion(self, window_ms=100, include_y=False):
        """Enable cumulative X motion and an absolute-motion rolling window.

        This must be called before acquisition starts.  Positive and negative
        totals contain magnitudes in sensor counts and are never reset by a
        thresholded motion event. include_y adds an independent Y window for
        tasks that explicitly request it; the default remains X-only.
        """
        assert not self.acquiring, (
            'Continuous motion must be configured before acquisition starts'
        )
        assert window_ms > 0, 'Continuous motion window must be positive'

        window_samples = int(round(
            self.data_chx.sampling_rate * window_ms / 1000
        ))
        assert window_samples >= 1, (
            'Continuous motion window is shorter than one sensor sample'
        )

        self.continuous_motion_enabled = True
        self.continuous_window_samples = window_samples
        self.continuous_window_ms = int(round(
            1000 * window_samples / self.data_chx.sampling_rate
        ))
        self._x_window = [0] * window_samples
        self.continuous_y_enabled = bool(include_y)
        self._y_window = [0] * window_samples if include_y else []
        self._reset_continuous_motion()

    def _reset_continuous_motion(self):
        """Reset cumulative counters and the rolling absolute-X window."""
        self.x_positive_total = 0
        self.x_negative_total = 0
        self.x_window_abs_total = 0
        self.y_window_abs_total = 0
        self.x_window_sample_count = 0
        self._x_window_index = 0

        for i in range(len(self._x_window)):
            self._x_window[i] = 0
        for i in range(len(self._y_window)):
            self._y_window[i] = 0

    def get_x_motion_snapshot(self):
        """Return an interrupt-safe snapshot of continuous X-motion counts.

        Values are (positive_total, negative_total, rolling_absolute_total,
        populated_window_samples).  Negative motion is returned as a positive
        magnitude in negative_total.
        """
        assert self.continuous_motion_enabled, (
            'Continuous motion has not been configured'
        )

        irq_state = pyb.disable_irq()
        positive_total = self.x_positive_total
        negative_total = self.x_negative_total
        window_abs_total = self.x_window_abs_total
        window_sample_count = self.x_window_sample_count
        pyb.enable_irq(irq_state)

        return (
            positive_total,
            negative_total,
            window_abs_total,
            window_sample_count,
        )

    def get_xy_motion_snapshot(self):
        """Read optional X/Y windows independently of transport buffers."""
        assert self.continuous_motion_enabled and self.continuous_y_enabled, (
            'Configure continuous motion with include_y=True first'
        )
        irq_state = pyb.disable_irq()
        positive_total = self.x_positive_total
        negative_total = self.x_negative_total
        x_total = self.x_window_abs_total
        y_total = self.y_window_abs_total
        count = self.x_window_sample_count
        pyb.enable_irq(irq_state)
        return positive_total, negative_total, x_total, y_total, count

    def _update_continuous_motion(self):
        """Update continuous counters from the latest sample in the ISR."""
        if not self.continuous_motion_enabled:
            return

        if self._delta_x >= 0:
            absolute_dx = self._delta_x
            self.x_positive_total += self._delta_x
        else:
            absolute_dx = -self._delta_x
            self.x_negative_total += absolute_dx

        if self.x_window_sample_count < self.continuous_window_samples:
            self.x_window_sample_count += 1
        else:
            self.x_window_abs_total -= self._x_window[
                self._x_window_index
            ]
            if self.continuous_y_enabled:
                self.y_window_abs_total -= self._y_window[self._x_window_index]

        self._x_window[self._x_window_index] = absolute_dx
        self.x_window_abs_total += absolute_dx
        if self.continuous_y_enabled:
            absolute_dy = abs(self._delta_y)
            self._y_window[self._x_window_index] = absolute_dy
            self.y_window_abs_total += absolute_dy
        self._x_window_index = (
            self._x_window_index + 1
        ) % self.continuous_window_samples

    def configure_diagnostics(self, sample_count=500):
        """Capture up to 1000 full bursts in RAM; no logging in the ISR.

        Configure before acquisition. Capture stops when full. The normal task
        path retains only one inactive-flag check and allocates no capture RAM.
        """
        assert not self.acquiring, 'Configure diagnostics before acquisition'
        assert isinstance(sample_count, int) and 1 <= sample_count <= 1000
        self._diagnostic_active = False
        self._diagnostic_ms = array('I', [0] * sample_count)
        self._diagnostic_ticks = array('I', [0] * sample_count)
        self._diagnostic_read_us = array('I', [0] * sample_count)
        self._diagnostic_x = bytearray(12 * sample_count)
        self._diagnostic_y = bytearray(12 * sample_count)
        self.diagnostic_capacity = sample_count
        self.diagnostic_count = 0
        self._diagnostic_active = True

    def _capture_diagnostics(self, timestamp, ticks_us, read_us):
        index = self.diagnostic_count
        self._diagnostic_ms[index] = timestamp
        self._diagnostic_ticks[index] = ticks_us
        self._diagnostic_read_us[index] = read_us
        offset = index * 12
        for i in range(12):
            self._diagnostic_x[offset + i] = self.x_buffer[i]
            self._diagnostic_y[offset + i] = self.y_buffer[i]
        # Publish last: main-loop readers never see a partly copied record.
        self.diagnostic_count = index + 1
        if self.diagnostic_count == self.diagnostic_capacity:
            self._diagnostic_active = False

    def get_diagnostic_sample(self, index):
        """Return one completed record from main-loop code, never an ISR.

        Burst layout: motion, observation, dx low/high, dy low/high, SQUAL,
        raw sum/max/min, shutter upper/lower. No field is used to erase zeros
        or to infer that an animal stopped. ticks_us wraps per time.ticks_us().
        """
        if not 0 <= index < self.diagnostic_count:
            raise IndexError('Diagnostic sample not available')
        offset = index * 12
        return {
            'time_ms': self._diagnostic_ms[index],
            'ticks_us': self._diagnostic_ticks[index],
            'read_us': self._diagnostic_read_us[index],
            'x': tuple(self._diagnostic_x[offset:offset + 12]),
            'y': tuple(self._diagnostic_y[offset:offset + 12]),
        }

    def get_diagnostics_status(self):
        """Main-loop summary; identity does not establish optical health."""
        return {
            'count': self.diagnostic_count,
            'capacity': self.diagnostic_capacity,
            'complete': bool(self.diagnostic_capacity and
                             self.diagnostic_count == self.diagnostic_capacity),
            'fault': self.acquisition_fault,
            'fault_axis': self.fault_axis,
            'init_attempts': self.init_attempts,
            'identity_x': (self.sensor_x.product_id, self.sensor_x.revision)
                          if self.sensor_x else None,
            'identity_y': (self.sensor_y.product_id, self.sensor_y.revision)
                          if self.sensor_y else None,
        }

    def read_sample(self):
        """read motion in the interrupt routine"""
        # Read motion in y direction
        self._reading_axis = 2
        self.sensor_y.read_burst(self.y_buffer_mv)
        self._delta_y = twos_comp(int.from_bytes(self.delta_y_mv, 'little'))

        time.sleep_us(100)

        # Read motion in x direction
        self._reading_axis = 1
        self.sensor_x.read_burst(self.x_buffer_mv)
        self._delta_x = twos_comp(int.from_bytes(self.delta_x_mv, 'little'))
        self._reading_axis = 0
        
        # Record accumulated motion
        self.delta_y += self._delta_y
        self.delta_x += self._delta_x
        
    def _timer_ISR(self, t):
        """Read a sample to the buffer, update write index."""
        timestamp = fw.current_time
        capture = self._diagnostic_active
        if capture:
            ticks_us = time.ticks_us()
        try:
            self.read_sample()
        except Exception:
            # Main-loop fault polling reports this even if the event queue is
            # full. Never retry/reset hardware or format an exception in an ISR.
            self.acquisition_fault = 1
            self.fault_axis = self._reading_axis
            self._diagnostic_active = False
            self.timer.callback(None)
            return
        if capture:
            self._capture_diagnostics(
                timestamp, ticks_us, time.ticks_diff(time.ticks_us(), ticks_us))
        self._update_continuous_motion()
        self.data_chx.put(self._delta_x, timestamp)
        self.data_chy.put(self._delta_y, timestamp)

        if (
            self.rising_event_ID
            and self.delta_x**2 + self.delta_y**2 >= self._threshold
        ):
            self.x = self.delta_x
            self.y = self.delta_y
            self.reset_delta()
            self.timestamp = fw.current_time
            interrupt_queue.put(self.ID)

    def _process_interrupt(self):
        if self.acquisition_fault:
            raise RuntimeError('Motion sensor read failed (axis code {}: 1=X, 2=Y)'.format(
                self.fault_axis))
        Analog_input._process_interrupt(self)

    def _stop_acquisition(self):
        """Quiesce sampling before sealing channels, even on shutdown errors."""
        self.timer.deinit()
        self.acquiring = False
        self._diagnostic_active = False
        error = None
        try:
            for channel in (self.data_chx, self.data_chy):
                try:
                    channel.stop()
                except Exception as caught:
                    if error is None:
                        error = caught
            if self._sensors_ready:
                for sensor in (self.sensor_x, self.sensor_y):
                    try:
                        sensor.shut_down(deinitSPI=False)
                    except Exception as caught:
                        if error is None:
                            error = caught
                try:
                    self.sensor_y.spi.deinit()
                except Exception as caught:
                    if error is None:
                        error = caught
        finally:
            self._sensors_ready = False
            self._deactivate_lines()
            self.reset_delta()
            self.x, self.y = 0, 0
        if error is not None:
            raise error

    def _start_acquisition(self):
        """Start sampling analog input values"""
        if not self._sensors_ready:
            self._initialise_sensors()
        if self.continuous_motion_enabled:
            self._reset_continuous_motion()
        try:
            self.timer.init(freq=self.data_chx.sampling_rate)
            self.timer.callback(self._timer_ISR)
            self.acquiring = True
        except Exception:
            self.timer.deinit()
            self._deactivate_lines()
            raise

    def record(self):
        """Start streaming data to computer."""
        # Fallback for direct/bench callers outside the framework lifecycle.
        if not self._sensors_ready:
            self._initialise_sensors()
        try:
            irq_state = pyb.disable_irq()
            try:
                self.data_chx.record()
                self.data_chy.record()
            finally:
                pyb.enable_irq(irq_state)
            if not self.acquiring:
                self._start_acquisition()
        except Exception:
            try:
                self._stop_acquisition()
            except Exception:
                pass  # Preserve the original recording/startup error.
            raise

    def stop(self):
        """Stop both streams; event-driven acquisition may remain enabled."""
        if self.threshold_active:
            irq_state = pyb.disable_irq()
            try:
                try:
                    self.data_chx.stop()
                finally:
                    self.data_chy.stop()
            finally:
                pyb.enable_irq(irq_state)
        else:
            self._stop_acquisition()

class PAA5100JE_firmware():
    def __init__(self):
        self.name = "firmware"

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
        """Write a group of commands into registers"""
        for x in range(0, len(data), 2):
            register, value = data[x : x + 2]
            if register == WAIT:
                time.sleep_ms(value)
            else:
                self._write(register, value)
                
    def _write(self, register: bytes, value: bytes):
        if self._spi_cs_gpio:
            self.set_pin(self._spi_cs_gpio, 0)
        self.spi.write(bytearray([register | 0x80, value]))
        if self._spi_cs_gpio:
            self.set_pin(self._spi_cs_gpio, 1)
            
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

from spidev import SpiDev

"""
On the MCP3008:
For one sample, 3 Bytes are transmitted to the MCP and 3 Bytes are read back;
at 200ksps that means that the max SPI Clock *should* be 6*200*1000 Hz...
On the other hand, the manual states "f_CLK = 18 * f_SAMPLE" (page 11)
So, we want 18 * 200 000 = 3.6MHz

On the Raspberry Pi 3:
Bus_Hz is 250MHz. We can divide this by 2 (multiple times) to set SPI rate:
250MHz / 2 = 125 MHz (faster is not possible)
(...)
250MHz / 64 = 3906250 Hz (3.9 MHz)
"""

class MCP3008:
    def __init__(self, bus = 0, device = 0):
        self.bus, self.device = bus, device
        self.spi = SpiDev()
        self.open()

    def open(self):
        self.spi.open(self.bus, self.device)
        # "The devices are capable of conversion rates of up to 200 ksps" see
        # above
        # That would be 18 * 200 000 = 3.6MHz
        # Let's set this to the next upper bound 3.9MHz (cdiv = 64)
        self.spi.max_speed_hz = 250000000 / 64 # = 3.9M
        # testing with 18*4096Hz
#        self.spi.max_speed_hz = 18 * 4096

    def read(self, channel = 0):
        adc = self.spi.xfer2([1, (8 + channel) << 4, 0])
        data = ((adc[1] & 3) << 8) + adc[2]
        return data

    def readdiff(self, channel=0):
        adc = self.spi.xfer2([1,channel << 4,0])
        data = ((adc[1] & 3) << 8) + adc[2]
        return data

    def close(self):
        self.spi.close()

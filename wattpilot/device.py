# WattPilot - Optimize your energy consumption
# Copyright (C) 2020 Cyril Jaquier
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import RPi.GPIO as GPIO


class Device:

    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

    def setup(self, pin):
        GPIO.setup(pin, GPIO.OUT)
        self.set_pin(pin, False)

    def cleanup(self):
        GPIO.cleanup()

    def set_pin(self, pin, value):
        assert isinstance(pin, int)
        assert isinstance(value, bool)
        GPIO.output(pin, GPIO.LOW if value else GPIO.HIGH)

    def get_pin(self, pin):
        return GPIO.input(pin) == GPIO.LOW


class TempSensorDevice:

    CRE = re.compile(r" t=(-?\d+)$")

    def __init__(self, name, address, offset=0.0):
        self.__address = address
        self.__path = "/sys/bus/w1/devices/%s/w1_slave" % address
        self.__offset = offset

    def __read_temp_raw(self):
        with open(self.__path, "r") as f:
            return [line.strip() for line in f.readlines()]

    def value(self):
        # Retry up to 3 times
        try:
            for _ in range(3):
                raw = self.__read_temp_raw()
                if len(raw) == 2:
                    crc, data = raw
                    if crc.endswith("YES"):
                        logger.debug("Temp sensor raw data: %s" % str(data))
                        # CRC valid, read the data
                        match = TempSensorDevice.CRE.search(data)
                        temperature = int(match.group(1)) / 1000. + self.__offset if match else None
                        # Range check, sometimes bad values pass the CRC check
                        if 5 < temperature < 100:
                            return temperature
                        else:
                            logger.debug("Temp outside range: %f" % temperature)
                    else:
                        logger.debug("Bad CRC: %s" % str(raw))
                time.sleep(0.1)
        except OSError:
            logger.exception("Unable to read temperature (%s)" % self.name)
        return None

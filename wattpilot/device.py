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

import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Final

from .temperature import Sensor

logger = logging.getLogger(__name__)


class Gpio(ABC):
    @abstractmethod
    def setup(self, pin: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def cleanup(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_pin(self, pin: int, value: bool) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_pin(self, pin: int) -> bool:
        raise NotImplementedError


class GpioDevice(Gpio):
    def __init__(self) -> None:
        import RPi.GPIO as GPIO

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

    def setup(self, pin: int) -> None:
        import RPi.GPIO as GPIO

        GPIO.setup(pin, GPIO.OUT)
        self.set_pin(pin, False)

    def cleanup(self) -> None:
        import RPi.GPIO as GPIO

        GPIO.cleanup()

    def set_pin(self, pin: int, value: bool) -> None:
        import RPi.GPIO as GPIO

        assert isinstance(pin, int)
        assert isinstance(value, bool)
        GPIO.output(pin, GPIO.LOW if value else GPIO.HIGH)

    def get_pin(self, pin: int) -> bool:
        import RPi.GPIO as GPIO

        return GPIO.input(pin) == GPIO.LOW


class TempSensorDevice(Sensor):
    CRE: Final = re.compile(r" t=(-?\d+)$")

    def __init__(self, name: str, address: str, offset: float = 0.0) -> None:
        self.__name: str = name
        self.__address: str = address
        self.__path: str = f"/sys/bus/w1/devices/{address}/w1_slave"
        self.__offset: float = offset

    def __read_temp_raw(self) -> list[str]:
        with open(self.__path) as f:
            return [line.strip() for line in f.readlines()]

    def value(self) -> float | None:
        # Retry up to 3 times
        try:
            for _ in range(3):
                raw = self.__read_temp_raw()
                if len(raw) == 2:
                    crc, data = raw
                    if crc.endswith("YES"):
                        logger.debug(f"Temp sensor raw data: {data!s}")
                        # CRC valid, read the data
                        match = TempSensorDevice.CRE.search(data)
                        temperature = int(match.group(1)) / 1000.0 + self.__offset if match else None
                        # Range check, sometimes bad values pass the CRC check
                        if temperature is not None and 5 < temperature < 100:
                            return temperature
                        elif temperature is not None:
                            logger.debug(f"Temp outside range: {temperature:f}")
                    else:
                        logger.debug(f"Bad CRC: {raw!s}")
                time.sleep(0.1)
        except OSError:
            logger.exception(f"Unable to read temperature ({self.__name})")
        return None

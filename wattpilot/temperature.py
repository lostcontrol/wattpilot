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

import configparser
import logging
from abc import ABC, abstractmethod

from .actor import WattPilotActor


class Sensor(ABC):
    @abstractmethod
    def value(self) -> float | None:
        raise NotImplementedError


class Temperature(WattPilotActor):
    def __init__(self, config: configparser.ConfigParser, sensor: Sensor) -> None:
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.__sensor: Sensor = sensor
        self.__temperature: float = 100.0

    def run(self, delay: float | int = 60) -> None:
        self.run_internal(delay)

    def run_internal(self, delay: float | int) -> None:
        try:
            val = self.__sensor.value()
            self.__temperature = 100.0 if val is None else float(val)
            self.logger.info("Temperature: %.1f", self.__temperature)
        except OSError:
            self.logger.exception("Unable to read temperature. Returning high value")
            self.__temperature = 100.0
        finally:
            self.do_delay(delay, "run_internal", args=[delay])

    def get_temperature(self) -> float:
        return self.__temperature

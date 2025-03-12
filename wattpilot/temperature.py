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

from .actor import WattPilotActor


class Temperature(WattPilotActor):

    def __init__(self, config, sensor):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.__sensor = sensor
        self.__temperature = 100

    def run(self, delay=60):
        self.run_internal(delay)

    def run_internal(self, delay):
        try:
            self.__temperature = self.__sensor.value()
            self.logger.info("Temperature: %.1f", self.__temperature)
        except OSError:
            self.logger.exception("Unable to read temperature. Returning high value")
            self.__temperature = 100
        finally:
            self.do_delay(delay, "run_internal", args=[delay])

    def get_temperature(self):
        return self.__temperature

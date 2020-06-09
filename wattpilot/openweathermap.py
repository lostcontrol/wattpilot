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

import json
import logging
import urllib
from datetime import datetime
import socket

from .actor import WattPilotActor


class OpenWeatherMap(WattPilotActor):

    def __init__(self, config):
        super().__init__()

        self.logger = logging.getLogger(__name__)

        lat = config.get("openweathermap", "lat")
        lon = config.get("openweathermap", "lon")
        key = config.get("openweathermap", "key")

        host = "api.openweathermap.org"
        self.__url = f"https://{host}/data/2.5/onecall?lat={lat}&lon={lon}&appid={key}"
        self.__last_update = 0
        self.__cloud = 100

    def download(self):
        with urllib.request.urlopen(self.__url, timeout=10) as f:
            return f.read().decode("ascii")

    def update_forecast(self):
        now = datetime.now().timestamp()
        # Update once an hour max.
        if self.__last_update + 1 * 3600 > now:
            self.logger.debug("Forecast updated %d seconds ago. Skipping", now - self.__last_update)
            return

        try:
            document = json.loads(self.download())
            for forecast in document["daily"]:
                timestamp = forecast["dt"]
                if timestamp > now:
                    self.__cloud = forecast["clouds"]
                    self.__last_update = now
                    self.logger.info("Updated forecast. Timestamp: %s Cloud: %d%%",
                                     datetime.fromtimestamp(timestamp), self.__cloud)
                    return self.__cloud
        except socket.timeout:
            self.logger.error("Timeout connecting to %s", self.__host)

    def is_tomorrow_sunny(self):
        return self.__cloud < 75

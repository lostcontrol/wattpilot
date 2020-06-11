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
        self.__cloud = 100

    def download(self):
        with urllib.request.urlopen(self.__url, timeout=10) as f:
            return f.read().decode("ascii")

    @staticmethod
    def __get_cloudiness(document):
        now = datetime.now().timestamp()
        for forecast in document["daily"]:
            timestamp = forecast["dt"]
            if timestamp > now:
                return timestamp, forecast["clouds"]
        return 0, 100

    def run(self, delay=3600):
        self.run_internal(delay)

    def run_internal(self, delay):
        try:
            document = json.loads(self.download())
            self.__cloud = self.__get_cloudiness(document)
            timestamp, cloudiness = self.__cloud
            readable_time = datetime.fromtimestamp(timestamp)
            self.logger.info("Forecast. Timestamp: %s Cloud: %d%%", readable_time, cloudiness)
        except socket.timeout:
            self.logger.error("Timeout connecting to %s", self.__host)
        except urllib.error.URLError as exception:
            self.logger.error("Unable to download data: %s", str(exception.reason))
        finally:
            self.do_delay(delay, "run_internal", args=[delay])

    def get_forecast(self):
        return self.__cloud

    def get_cloudiness(self):
        return self.__cloud[1]

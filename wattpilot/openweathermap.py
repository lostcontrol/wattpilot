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
import json
import logging
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from .actor import WattPilotActor


class OpenWeatherMap(WattPilotActor):
    def __init__(self, config: configparser.ConfigParser) -> None:
        super().__init__()

        self.logger = logging.getLogger(__name__)

        lat = config.get("openweathermap", "lat")
        lon = config.get("openweathermap", "lon")
        key = config.get("openweathermap", "key")

        self.__host = "api.openweathermap.org"
        self.__url = f"https://{self.__host}/data/2.5/forecast?lat={lat}&lon={lon}&appid={key}"
        self.__cloud: tuple[int, int] = (0, 100)

    def download(self) -> str:
        with urllib.request.urlopen(self.__url, timeout=10) as f:
            return f.read().decode("utf-8")

    @staticmethod
    def __get_cloudiness(document: dict[str, Any]) -> tuple[int, int]:
        now = datetime.now(tz=UTC).timestamp()
        for forecast in document["list"]:
            timestamp = forecast["dt"]
            if timestamp > now:
                return timestamp, forecast["clouds"]["all"]
        return 0, 100

    def run(self, delay: float | int = 3600) -> None:
        self.run_internal(delay)

    def run_internal(self, delay: float | int) -> None:
        try:
            document = json.loads(self.download())
            self.__cloud = self.__get_cloudiness(document)
            timestamp, cloudiness = self.__cloud
            readable_time = datetime.fromtimestamp(timestamp, tz=UTC)
            self.logger.info("Forecast. Timestamp: %s Cloud: %d%%", readable_time, cloudiness)
        except TimeoutError:
            self.logger.error("Timeout connecting to %s", self.__host)
        except urllib.error.URLError as exception:
            self.logger.error("Unable to download data: %s", str(exception.reason))
        finally:
            self.do_delay(delay, "run_internal", args=[delay])

    def get_forecast(self) -> tuple[int, int]:
        return self.__cloud

    def get_cloudiness(self) -> int:
        return self.__cloud[1]

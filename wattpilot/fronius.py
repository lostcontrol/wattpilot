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

import collections
import json
import logging
import urllib.request
import socket
import statistics

from .actor import WattPilotActor


class EnergyReading:

    def __init__(self, document):
        self.__node = document["Body"]["Data"]["0"]

    @property
    def timestamp(self):
        return self.__node["TimeStamp"]

    @property
    def consumed(self):
        return self.__node["EnergyReal_WAC_Sum_Consumed"]

    @property
    def produced(self):
        return self.__node["EnergyReal_WAC_Sum_Produced"]


class AverageReadings:

    def __init__(self, maxlen=3):
        self.__queue = collections.deque(maxlen=maxlen)

    def clear(self):
        self.__queue.clear()

    def append(self, value):
        self.__queue.append(value)

    def average(self):
        return statistics.mean(self.__queue) if self.__queue else 0


class Fronius(WattPilotActor):

    def __init__(self, config):
        super().__init__()

        self.logger = logging.getLogger(__name__)

        self.__host = config.get("main", "fronius_host")
        self.__url = f"http://{self.__host}/solar_api/v1/GetMeterRealtimeData.cgi?Scope=System"

        self.__callback = None
        self.__last_reading = None
        self.__power = AverageReadings(maxlen=2)

    def download(self):
        with urllib.request.urlopen(self.__url, timeout=5) as f:
            return f.read().decode("ascii")

    @staticmethod
    def compute_power(reading1, reading2):
        assert reading1.timestamp <= reading2.timestamp
        duration = reading2.timestamp - reading1.timestamp
        if duration == 0:
            return 0
        consumed = reading2.consumed - reading1.consumed
        produced = reading2.produced - reading1.produced
        return (consumed - produced) * 3600 / duration

    def register_callback(self, callback):
        self.logger.info("Register callback: %s", callback)
        self.__callback = callback

    def run(self, delay=30):
        self.__last_reading = None
        self.__power.clear()
        self.run_internal(delay)

    def run_internal(self, delay):
        try:
            reading = EnergyReading(json.loads(self.download()))
            self.logger.debug("Consumed: %dWh Produced: %dWh", reading.consumed, reading.produced)
            if self.__last_reading:
                power = self.compute_power(self.__last_reading, reading)
                self.logger.info("Power: %.2fW", power)
                self.__power.append(power)
                if self.__callback:
                    self.__callback.defer()
            self.__last_reading = reading
        except socket.timeout:
            self.logger.error("Timeout connecting to %s", self.__host)
        except urllib.error.URLError as exception:
            self.logger.error("Unable to download data: %s", str(exception.reason))
        finally:
            self.do_delay(delay, "run_internal", args=[delay])

    def get_power(self):
        return self.__power.average()


if __name__ == "__main__":
    import configparser
    import time
    import pykka

    ini = """
    [main]
    fronius_host = fronius
    """
    configuration = configparser.ConfigParser()
    configuration.read_string(ini)
    try:
        fronius = Fronius.start(configuration).proxy()
        print(fronius.download().get())
        fronius.run.defer()
        for _ in range(10):
            time.sleep(30)
            print(fronius.power().get())
    finally:
        pykka.ActorRegistry.stop_all()

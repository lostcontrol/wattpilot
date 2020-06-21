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

from datetime import datetime
import socket
import urllib
import logging

from .actor import WattPilotActor


class PVOutput(WattPilotActor):

    def __init__(self, config, temperature):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        self.__temperature = temperature

        key = config.get("pvoutput", "key")
        sid = config.get("pvoutput", "sid")
        field = config.get("pvoutput", "field")

        base_url = "https://pvoutput.org/service/r2/addstatus.jsp"
        self.__url = f"{base_url}?key={key}&sid={sid}&d={{date}}&t={{time}}&{field}={{temperature}}"

    def send_temperature(self, temperature):
        now = datetime.now()
        date = now.strftime("%Y%m%d")
        time = now.strftime("%H:%M")
        url = self.__url.format(date=date, time=time, temperature=temperature)
        self.logger.debug("Sending %s", url)
        with urllib.request.urlopen(url) as f:
            # OK 200: Added Status
            response = f.read(300)
            self.logger.debug(response)

    def run(self, delay=300):
        self.run_internal(delay)

    def run_internal(self, delay):
        try:
            temperature = self.__temperature.get_temperature().get()
            self.send_temperature(temperature)
        except socket.timeout:
            self.logger.error("Timeout connecting to pvoutput.org")
        except urllib.error.URLError as exception:
            self.logger.error("Unable to download data: %s", str(exception.reason))
        finally:
            self.do_delay(delay, "run_internal", args=[delay])

    def get_temperature(self):
        return self.__temperature

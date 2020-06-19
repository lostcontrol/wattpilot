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

import argparse
import connexion
import unittest.mock
import configparser
import logging.config
import signal
import os
import pykka
import flask_cors

from wattpilot.app import WattPilotApp
from wattpilot.wattpilot import WattPilot
from wattpilot.fronius import Fronius
from wattpilot.openweathermap import OpenWeatherMap
from wattpilot.temperature import Temperature
from wattpilot.device import GpioDevice, TempSensorDevice


def config():
    configuration = configparser.ConfigParser()
    configuration.read(["config.ini", "config.ini.local"])
    return configuration


def setup_logging(log_config):
    if os.path.isfile(log_config):
        logging.config.fileConfig(log_config, disable_existing_loggers=False)


def handle_sigterm(*args):
    raise KeyboardInterrupt()


def main():
    # Docker stop containers using SIGTERM
    signal.signal(signal.SIGTERM, handle_sigterm)

    setup_logging("logging.conf")

    parser = argparse.ArgumentParser()
    parser.add_argument("--fake-devices", action="store_true", help="fake the underlying hardware")
    args = parser.parse_args()

    configuration = config()

    power = Fronius.start(configuration).proxy()
    weather = OpenWeatherMap.start(configuration).proxy()

    if args.fake_devices:
        gpio = unittest.mock.Mock()
        temperature_sensor = unittest.mock.Mock()
        temperature_sensor.value.return_value = 56.7
    else:
        gpio = GpioDevice()
        temperature_sensor = TempSensorDevice("boiler", configuration.get("temperature", "address"))

    temperature = Temperature.start(configuration, temperature_sensor).proxy()
    wattpilot = WattPilot.start(configuration, power, gpio, weather, temperature).proxy()

    WattPilotApp.wattpilot = wattpilot
    WattPilotApp.openweathermap = weather
    WattPilotApp.temperature = temperature

    temperature.run.defer()
    wattpilot.idle.defer()

    app = connexion.FlaskApp(__name__, specification_dir="openapi/")
    app.add_api("swagger.yaml")

    flask_cors.CORS(app.app)

    try:
        app.run(port=8080)
    finally:
        wattpilot.halt().get()
        pykka.ActorRegistry.stop_all()
        gpio.cleanup()


if __name__ == "__main__":
    main()

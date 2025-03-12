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
import configparser
import logging.config
import os
import signal
import unittest.mock

import connexion
import flask_cors
import pykka

from wattpilot.app import WattPilotApp
from wattpilot.device import GpioDevice, TempSensorDevice
from wattpilot.fronius import Fronius
from wattpilot.openweathermap import OpenWeatherMap
from wattpilot.pvoutput import PVOutput
from wattpilot.temperature import Temperature
from wattpilot.wattpilot import WattPilot


def config():
    configuration = configparser.ConfigParser()
    configuration.read(["config.ini", "config.ini.local"])
    return configuration


def setup_logging(log_config):
    if os.path.isfile(log_config):
        logging.config.fileConfig(log_config, disable_existing_loggers=False)


def handle_sigterm(*args):
    raise KeyboardInterrupt


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
    pvoutput = PVOutput.start(configuration, temperature).proxy()
    wattpilot = WattPilot.start(configuration, power, gpio, weather, temperature).proxy()

    WattPilotApp.wattpilot = wattpilot
    WattPilotApp.openweathermap = weather
    WattPilotApp.temperature = temperature

    # Wait for the first temperature to be read
    temperature.run().get()
    pvoutput.run.defer()

    wattpilot.idle.defer()

    app = connexion.FlaskApp(__name__, specification_dir="openapi/")
    app.add_api("swagger.yaml")

    flask_cors.CORS(app.app)

    try:
        app.run(host="0.0.0.0", port=8080)
    finally:
        wattpilot.halt().get()
        pykka.ActorRegistry.stop_all()
        gpio.cleanup()


if __name__ == "__main__":
    main()

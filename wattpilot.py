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
import threading
import unittest.mock

import pykka

from frontend.app import FrontendApp
from frontend.service import BackendService
from frontend.store import SnapshotStore
from wattpilot.device import Gpio, GpioDevice, TempSensorDevice
from wattpilot.fronius import Fronius
from wattpilot.openweathermap import OpenWeatherMap
from wattpilot.pvoutput import PVOutput
from wattpilot.settings import DEFAULT_SETTINGS_FILE, SettingsFile
from wattpilot.temperature import Sensor, Temperature
from wattpilot.wattpilot import WattPilot


def config(settings_path: str | None = None) -> configparser.ConfigParser:
    configuration = configparser.ConfigParser()
    path = settings_path or os.environ.get("WATTPILOT_SETTINGS", DEFAULT_SETTINGS_FILE)
    configuration.read(["config.ini", "config.ini.local", path])
    return configuration


def setup_logging(log_config: str) -> None:
    if os.path.isfile(log_config):
        logging.config.fileConfig(log_config, disable_existing_loggers=False)


def main() -> None:
    setup_logging("logging.conf")

    parser = argparse.ArgumentParser()
    parser.add_argument("--fake-devices", action="store_true", help="fake the underlying hardware")
    args = parser.parse_args()

    settings_file = SettingsFile()
    configuration = config(str(settings_file.path))

    power: pykka.ActorProxy[Fronius] = Fronius.start(configuration).proxy()
    weather: pykka.ActorProxy[OpenWeatherMap] = OpenWeatherMap.start(configuration).proxy()

    gpio: Gpio
    temperature_sensor: Sensor
    if args.fake_devices:
        gpio = unittest.mock.Mock()
        mock_sensor = unittest.mock.Mock()
        mock_sensor.value.return_value = 56.7
        temperature_sensor = mock_sensor
    else:
        gpio = GpioDevice()
        temperature_sensor = TempSensorDevice("boiler", configuration.get("temperature", "address"))

    temperature: pykka.ActorProxy[Temperature] = Temperature.start(configuration, temperature_sensor).proxy()
    pvoutput: pykka.ActorProxy[PVOutput] = PVOutput.start(configuration, temperature).proxy()
    wattpilot: pykka.ActorProxy[WattPilot] = WattPilot.start(configuration, power, gpio, weather, temperature).proxy()

    pin_to_name = {
        configuration.getint(sec, "pin"): sec.removeprefix("load_")
        for sec in configuration.sections()
        if sec.startswith("load_") and configuration.has_option(sec, "pin")
    }
    service = BackendService(
        wattpilot,
        weather,
        temperature,
        load_names=pin_to_name,
        settings_file=settings_file,
    )
    store = SnapshotStore(service)

    # Wait for the first temperature to be read
    temperature.run().get()
    pvoutput.run.defer()

    wattpilot.idle.defer()

    cleaned_up = threading.Event()

    def cleanup() -> None:
        # May be called from both the shutdown hook and the error path: run only once.
        if cleaned_up.is_set():
            return
        cleaned_up.set()
        try:
            wattpilot.halt().get(timeout=10)
        finally:
            pykka.ActorRegistry.stop_all()
            gpio.cleanup()

    try:
        frontend_app = FrontendApp(store, cleanup)
        frontend_app.run(host="0.0.0.0", port=8080)
    except Exception:
        cleanup()
        raise


if __name__ == "__main__":
    main()

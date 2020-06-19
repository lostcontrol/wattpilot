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

import pykka
import pytest

from wattpilot.device import TempSensorDevice
from wattpilot.temperature import Temperature


@pytest.fixture
def config():
    ini = """
        [temperature]
        address = 28-0416350909ff
    """
    configuration = configparser.ConfigParser()
    configuration.read_string(ini)
    return configuration


@pytest.fixture
def temperature_sensor(mocker):
    return mocker.Mock(spec=TempSensorDevice)


@pytest.fixture
def temperature(mocker, config, temperature_sensor):
    proxy = Temperature.start(config, temperature_sensor).proxy()
    yield proxy
    pykka.ActorRegistry.stop_all()


class TestTemperature:

    @pytest.mark.parametrize("value", [0, 10, 22.2, 56.7, 100])
    def test_read_temperature(self, value, temperature, temperature_sensor):
        temperature_sensor.value.return_value = value
        temperature.run.defer()
        assert temperature.get_temperature().get() == value

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
import os

import pykka
import pytest
from freezegun import freeze_time

from wattpilot.openweathermap import OpenWeatherMap


@pytest.fixture
def config():
    ini = """
        [openweathermap]
        lat = 46.687901
        lon = 6.898991
        key = 1234567890
    """
    configuration = configparser.ConfigParser()
    configuration.read_string(ini)
    return configuration


@pytest.fixture
def openweathermap(mocker, config):
    with freeze_time("2020-06-07 06:00:00"):
        openweathermap = OpenWeatherMap.start(config).proxy()
        yield openweathermap
        pykka.ActorRegistry.stop_all()


class TestOpenWeatherMap:

    @staticmethod
    def __read_json_asset(filename):
        with open(os.path.join("test/assets", f"{filename}.json")) as f:
            return f.read()

    @pytest.mark.parametrize(("asset", "cloud"), [
        ("weather01", 27),
        # ("weather02", 75),
        # ("weather03", 75),
    ])
    def test_update_forecast(self, asset, cloud, mocker, openweathermap):
        mocker.patch.object(OpenWeatherMap, "download").return_value = self.__read_json_asset(asset)
        openweathermap.run.defer()
        assert openweathermap.get_cloudiness().get() == cloud

    @pytest.mark.parametrize(("asset", "forecast"), [
        ("weather01", (1741651200, 27)),
        # ("weather02", (1591527600, 75)),
        # ("weather03", (1591527600, 75)),
    ])
    def test_get_forecast(self, asset, forecast, mocker, openweathermap):
        mocker.patch.object(OpenWeatherMap, "download").return_value = self.__read_json_asset(asset)
        openweathermap.run.defer()
        assert openweathermap.get_forecast().get() == forecast

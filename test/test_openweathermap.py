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

from freezegun import freeze_time
import pykka
import pytest

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
        with open(os.path.join("test/assets", f"{filename}.json"), "r") as f:
            return f.read()

    @pytest.mark.parametrize("asset,cloud", [
        ("weather01", 83),
        ("weather02", 75),
        ("weather03", 75),
    ])
    def test_update_forecast(self, asset, cloud, mocker, openweathermap):
        mocker.patch.object(OpenWeatherMap, "download").return_value = self.__read_json_asset(asset)
        assert openweathermap.update_forecast().get() == cloud

    def test_update_once_a_day(self, mocker, openweathermap):
        download_mock = mocker.patch.object(OpenWeatherMap, "download")
        download_mock.return_value = self.__read_json_asset("weather01")
        openweathermap.update_forecast().get()
        openweathermap.update_forecast().get()
        download_mock.assert_called_once()
        with freeze_time("2020-06-08 06:00:00"):
            openweathermap.update_forecast().get()
            assert download_mock.call_count == 2

    @pytest.mark.parametrize("asset,sunny", [
        ("weather01", False),
        ("weather02", True),
        ("weather03", True),
    ])
    def test_is_tomorrow_sunny(self, asset, sunny, mocker, openweathermap):
        mocker.patch.object(OpenWeatherMap, "download").return_value = self.__read_json_asset(asset)
        openweathermap.update_forecast.defer()
        openweathermap.is_tomorrow_sunny().get() == sunny

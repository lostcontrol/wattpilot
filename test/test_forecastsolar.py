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
from datetime import datetime
from pathlib import Path

import pykka
import pytest
from freezegun import freeze_time

from wattpilot.forecastsolar import ForecastSolar


@pytest.fixture
def config() -> configparser.ConfigParser:
    ini = """
        [main]
        schedule_start = 2

        [forecastsolar]
        latitude = 46.687761
        longitude = 6.898890
        declination = 20
        azimuth = 30
        kwp = 10.240
    """
    configuration = configparser.ConfigParser()
    configuration.read_string(ini)
    return configuration


@pytest.fixture
def forecastsolar(config: configparser.ConfigParser):
    with freeze_time("2022-01-03 06:00:00"):
        actor: pykka.ActorProxy[ForecastSolar] = ForecastSolar.start(config).proxy()
        yield actor
        pykka.ActorRegistry.stop_all()


class TestForecastSolar:
    @staticmethod
    def __read_json_asset(filename: str) -> str:
        asset_path = Path("test/assets") / f"{filename}.json"
        return asset_path.read_text(encoding="utf-8")

    def test_get_forecast_morning(self, mocker, forecastsolar) -> None:
        mocker.patch.object(ForecastSolar, "download").return_value = self.__read_json_asset("forecastsolar01")
        with freeze_time("2022-01-03 09:00:00"):
            forecastsolar.run.defer()
            # Morning (< 12:00): targets today (2022-01-03)
            assert forecastsolar.get_forecast().get() == ("2022-01-03", 15.3)
            assert forecastsolar.get_production().get() == pytest.approx(15.325)

    def test_get_forecast_afternoon(self, mocker, forecastsolar) -> None:
        mocker.patch.object(ForecastSolar, "download").return_value = self.__read_json_asset("forecastsolar01")
        with freeze_time("2022-01-03 14:00:00"):
            forecastsolar.run.defer()
            # Afternoon (>= 12:00): targets tomorrow (2022-01-04)
            assert forecastsolar.get_forecast().get() == ("2022-01-04", 7.5)
            assert forecastsolar.get_production().get() == pytest.approx(7.529)

    def test_get_forecast_missing_date(self, mocker, forecastsolar) -> None:
        mocker.patch.object(ForecastSolar, "download").return_value = '{"result": {"watt_hours_day": {}}}'
        forecastsolar.run.defer()
        assert forecastsolar.get_forecast().get() == (None, None)
        assert forecastsolar.get_production().get() == 0.0

    def test_optimal_delay_calculation(self, forecastsolar) -> None:
        # Schedule start = 2 (02:00). Target refresh = 01:45.
        now = datetime(2022, 1, 3, 1, 0, 0).astimezone()
        delay = forecastsolar.compute_next_delay(now, 14400).get()
        # 45 minutes = 2700 seconds
        assert delay == pytest.approx(2700.0)

        # Target refresh has just passed (now = 01:50) -> next target is tomorrow 01:45 (>4h away)
        now_passed = datetime(2022, 1, 3, 1, 50, 0).astimezone()
        delay_passed = forecastsolar.compute_next_delay(now_passed, 14400).get()
        assert delay_passed == 14400.0

    def test_config_full_names(self, forecastsolar) -> None:
        url = forecastsolar.get_url().get()
        assert url == "https://api.forecast.solar/estimate/46.687761/6.898890/20/30/10.240"

    def test_config_missing_option(self) -> None:
        ini = """
            [main]
            schedule_start = 2

            [forecastsolar]
            latitude = 46.123
        """
        configuration = configparser.ConfigParser()
        configuration.read_string(ini)
        with pytest.raises(configparser.NoOptionError):
            ForecastSolar(configuration)

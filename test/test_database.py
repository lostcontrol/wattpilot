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
from datetime import UTC, datetime
from pathlib import Path

import pykka
import pytest

from wattpilot.database import RETENTION_SECONDS, Database, MetricPoint
from wattpilot.forecastsolar import ForecastSolar
from wattpilot.fronius import Fronius
from wattpilot.temperature import Temperature
from wattpilot.wattpilot import MetricPoller, WattPilot


class FakeFuture:
    def __init__(self, value):
        self.value = value

    def get(self, timeout=None):
        return self.value


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_wattpilot.db"


@pytest.fixture
def database(db_path: Path):
    proxy = Database.start(path=db_path).proxy()
    yield proxy
    pykka.ActorRegistry.stop_all()


class TestDatabase:
    def test_record_and_get_history(self, database: pykka.ActorProxy[Database]):
        now = int(datetime.now(tz=UTC).timestamp())
        database.record(50.5, 1, timestamp=now - 120).get()
        database.record(52.0, 2, timestamp=now - 60).get()
        database.record(53.5, 0, timestamp=now).get()

        history: list[MetricPoint] = database.get_history().get()
        assert len(history) == 3
        assert history[0].temperature == 50.5
        assert history[0].loads == 1
        assert history[1].temperature == 52.0
        assert history[1].loads == 2
        assert history[2].temperature == 53.5
        assert history[2].loads == 0

    def test_get_history_since_timestamp(self, database: pykka.ActorProxy[Database]):
        now = int(datetime.now(tz=UTC).timestamp())
        database.record(48.0, 0, timestamp=now - 200).get()
        database.record(50.0, 1, timestamp=now - 100).get()
        database.record(51.0, 2, timestamp=now).get()

        filtered = database.get_history(since_timestamp=now - 150).get()
        assert len(filtered) == 2
        assert filtered[0].temperature == 50.0
        assert filtered[1].temperature == 51.0

    def test_retention_pruning(self, database: pykka.ActorProxy[Database]):
        now = int(datetime.now(tz=UTC).timestamp())
        expired_ts = now - RETENTION_SECONDS - 100

        # Insert an expired record directly
        database.record(40.0, 0, timestamp=expired_ts).get()
        # Verify it was inserted
        history = database.get_history(since_timestamp=expired_ts - 10).get()
        assert len(history) == 1

        # Inserting a new record should prune the expired record
        database.record(55.0, 3, timestamp=now).get()
        history_after = database.get_history(since_timestamp=expired_ts - 10).get()
        assert len(history_after) == 1
        assert history_after[0].temperature == 55.0
        assert history_after[0].timestamp == now


class TestWattPilotDatabaseIntegration:
    @pytest.fixture
    def config(self):
        ini = """
            [main]
            hysteresis_to_grid = 200
            hysteresis_from_grid = 0
            schedule_start = 2
            schedule_stop = 6
            solar_threshold = 15.0

            [temperature]
            temperature_schedule = 50
            temperature_solar = 60
            temperature_force = 55

            [load_1]
            power = 1000
            pin = 1

            [load_2]
            power = 2000
            pin = 2
        """
        configuration = configparser.ConfigParser()
        configuration.read_string(ini)
        return configuration

    def test_wattpilot_records_on_load_transitions(self, mocker, config, tmp_path: Path):
        power = mocker.Mock(spec=Fronius)
        power.get_power.return_value = FakeFuture(0)
        gpio = mocker.Mock()
        forecast = mocker.Mock(spec=ForecastSolar)
        temperature = mocker.Mock(spec=Temperature)
        temperature.get_temperature.return_value = FakeFuture(50.0)

        db_proxy = Database.start(path=tmp_path / "int_test.db").proxy()
        try:
            wp = WattPilot.start(config, power, gpio, forecast, temperature, database=db_proxy).proxy()

            # Transition from halt to idle, then to force
            wp.idle().get()
            wp.force().get()
            # Force mode enables all loads -> should record
            history = db_proxy.get_history().get()
            assert len(history) >= 1
            assert history[-1].loads == 2
            assert history[-1].temperature == 50.0

            # Halt mode stops all loads -> should record
            wp.halt().get()
            history = db_proxy.get_history().get()
            assert history[-1].loads == 0
        finally:
            pykka.ActorRegistry.stop_all()

    def test_metric_poller_samples_database(self, mocker, config, tmp_path: Path):
        power = mocker.Mock(spec=Fronius)
        gpio = mocker.Mock()
        forecast = mocker.Mock(spec=ForecastSolar)
        temperature = mocker.Mock(spec=Temperature)
        temperature.get_temperature.return_value = FakeFuture(58.4)

        db_proxy = Database.start(path=tmp_path / "poller_test.db").proxy()
        try:
            wp = WattPilot.start(config, power, gpio, forecast, temperature, database=db_proxy).proxy()
            poller = MetricPoller.start(db_proxy, temperature, wp).proxy()
            poller.run_internal(60).get()

            history = db_proxy.get_history().get()
            assert len(history) == 1
            assert history[0].temperature == 58.4
            assert history[0].loads == 0
        finally:
            pykka.ActorRegistry.stop_all()

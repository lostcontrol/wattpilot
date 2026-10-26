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
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from frontend.components import HistoryChart
from frontend.pages.control import ControlPage
from frontend.service import BackendService, Snapshot
from wattpilot.database import MetricPoint
from wattpilot.settings import (
    SettingsFile,
    get_schedule_duration,
    in_schedule_window,
    validate_hour,
    validate_settings,
    validate_solar_threshold,
    validate_temperature,
)


class TestScheduleWindow:
    def test_normal_window(self):
        # 02:00 to 06:00
        assert not in_schedule_window(1, 2, 6)
        assert in_schedule_window(2, 2, 6)
        assert in_schedule_window(3, 2, 6)
        assert in_schedule_window(5, 2, 6)
        assert not in_schedule_window(6, 2, 6)
        assert not in_schedule_window(7, 2, 6)

    def test_midnight_wrap_around(self):
        # 23:00 to 02:00 (3 hours: 23, 0, 1)
        assert not in_schedule_window(22, 23, 2)
        assert in_schedule_window(23, 23, 2)
        assert in_schedule_window(0, 23, 2)
        assert in_schedule_window(1, 23, 2)
        assert not in_schedule_window(2, 23, 2)
        assert not in_schedule_window(3, 23, 2)

    def test_equal_hours(self):
        for h in range(24):
            assert not in_schedule_window(h, 4, 4)

    def test_duration_calculation(self):
        assert get_schedule_duration(2, 6) == 4
        assert get_schedule_duration(23, 2) == 3
        assert get_schedule_duration(22, 6) == 8
        assert get_schedule_duration(5, 5) == 0


class TestSettingsValidation:
    def test_valid_temperatures(self):
        assert validate_temperature(45.0) == 45.0
        assert validate_temperature(65.0) == 65.0
        assert validate_temperature(55.5) == 55.5
        assert validate_temperature(50) == 50.0

    def test_invalid_temperatures(self):
        with pytest.raises(ValueError, match="must be between"):
            validate_temperature(44.5)
        with pytest.raises(ValueError, match="must be between"):
            validate_temperature(65.5)
        with pytest.raises(ValueError, match="must be a multiple"):
            validate_temperature(50.3)  # not a 0.5 step
        with pytest.raises(TypeError):
            validate_temperature(cast(Any, "50.0"))

    def test_valid_hours(self):
        assert validate_hour(0) == 0
        assert validate_hour(23) == 23
        assert validate_hour(12) == 12

    def test_invalid_hours(self):
        with pytest.raises(ValueError, match="must be between 0 and 23"):
            validate_hour(-1)
        with pytest.raises(ValueError, match="must be between 0 and 23"):
            validate_hour(24)
        with pytest.raises(TypeError):
            validate_hour(True)  # bool is subclass of int in Python
        with pytest.raises(TypeError):
            validate_hour(cast(Any, "2"))

    def test_valid_solar_threshold(self):
        assert validate_solar_threshold(0.0) == 0.0
        assert validate_solar_threshold(50.0) == 50.0
        assert validate_solar_threshold(15.0) == 15.0
        assert validate_solar_threshold(15.5) == 15.5
        assert validate_solar_threshold(15) == 15.0

    def test_invalid_solar_threshold(self):
        with pytest.raises(ValueError, match="must be between"):
            validate_solar_threshold(-0.5)
        with pytest.raises(ValueError, match="must be between"):
            validate_solar_threshold(50.5)
        with pytest.raises(ValueError, match="must be a multiple"):
            validate_solar_threshold(15.3)
        with pytest.raises(TypeError):
            validate_solar_threshold(True)
        with pytest.raises(TypeError):
            validate_solar_threshold(cast(Any, "15.0"))

    def test_validate_settings_success(self):
        validate_settings(
            temperature_schedule=50.0,
            temperature_solar=60.0,
            temperature_force=55.5,
            schedule_start=23,
            schedule_stop=2,
            solar_threshold=15.0,
        )

    def test_validate_settings_equal_hours(self):
        with pytest.raises(ValueError, match="cannot be equal"):
            validate_settings(
                temperature_schedule=50.0,
                temperature_solar=60.0,
                temperature_force=55.0,
                schedule_start=3,
                schedule_stop=3,
                solar_threshold=15.0,
            )


class TestSettingsFile:
    def test_save_and_load(self, tmp_path: Path):
        file_path = tmp_path / "test_settings.ini"
        sf = SettingsFile(file_path)

        # Initially empty
        assert sf.load() == {}

        # Save settings
        sf.save(
            {
                "temperature_schedule": 52.5,
                "temperature_solar": 62.0,
                "temperature_force": 50.0,
                "schedule_start": 23,
                "schedule_stop": 2,
                "solar_threshold": 16.5,
            }
        )

        loaded = sf.load()
        assert loaded["temperature_schedule"] == 52.5
        assert loaded["temperature_solar"] == 62.0
        assert loaded["temperature_force"] == 50.0
        assert loaded["schedule_start"] == 23
        assert loaded["schedule_stop"] == 2
        assert loaded["solar_threshold"] == 16.5

    def test_preserves_existing_config(self, tmp_path: Path):
        file_path = tmp_path / "custom.ini"
        file_path.write_text("[other]\ncustom_key = 123\n", encoding="utf-8")

        sf = SettingsFile(file_path)
        sf.save(
            {
                "temperature_schedule": 55.0,
                "schedule_start": 1,
                "schedule_stop": 5,
                "solar_threshold": 12.0,
            }
        )

        cp = configparser.ConfigParser()
        cp.read(file_path, encoding="utf-8")
        assert cp.get("other", "custom_key") == "123"
        assert cp.getfloat("temperature", "temperature_schedule") == 55.0
        assert cp.getint("main", "schedule_start") == 1
        assert cp.getint("main", "schedule_stop") == 5
        assert cp.getfloat("main", "solar_threshold") == 12.0

    def test_cascading_priority(self, tmp_path: Path):
        # 1. Base config
        base = tmp_path / "config.ini"
        base.write_text(
            "[main]\nschedule_start = 2\nschedule_stop = 6\n"
            "[temperature]\ntemperature_schedule = 50\ntemperature_solar = 60\ntemperature_force = 55\n",
            encoding="utf-8",
        )

        # 2. Local config
        local = tmp_path / "config.ini.local"
        local.write_text(
            "[main]\nschedule_start = 3\n[temperature]\ntemperature_schedule = 52\n",
            encoding="utf-8",
        )

        # 3. Settings config (highest priority)
        settings = tmp_path / "config.ini.settings"
        settings.write_text(
            "[main]\nschedule_start = 23\nschedule_stop = 2\n[temperature]\ntemperature_schedule = 54.5\n",
            encoding="utf-8",
        )

        cp = configparser.ConfigParser()
        cp.read([base, local, settings])

        # settings overrides local and base
        assert cp.getint("main", "schedule_start") == 23
        assert cp.getint("main", "schedule_stop") == 2
        assert cp.getfloat("temperature", "temperature_schedule") == 54.5
        # solar comes from base because not overridden
        assert cp.getfloat("temperature", "temperature_solar") == 60.0


class TestLocalesConsistency:
    def test_en_and_fr_have_same_keys(self):
        locales_dir = Path(__file__).parent.parent / "frontend" / "locales"
        en_data = json.loads((locales_dir / "en.json").read_text(encoding="utf-8"))
        fr_data = json.loads((locales_dir / "fr.json").read_text(encoding="utf-8"))

        def flatten(d: dict, prefix: str = "") -> set[str]:
            keys = set()
            for k, v in d.items():
                full = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys.update(flatten(v, full))
                else:
                    keys.add(full)
            return keys

        en_keys = flatten(en_data)
        fr_keys = flatten(fr_data)
        assert en_keys == fr_keys


class TestBackendServiceSettings:
    @pytest.mark.anyio
    async def test_backend_service_snapshot_and_set_settings(self, mocker, tmp_path: Path):
        wattpilot_mock = mocker.Mock()
        wattpilot_mock.get_state.return_value.get.return_value = "idle"
        wattpilot_mock.get_active_loads.return_value.get.return_value = []
        wattpilot_mock.get_schedule_trigger.return_value.get.return_value = False
        wattpilot_mock.get_scheduled_by_forecast.return_value.get.return_value = False
        wattpilot_mock.get_settings.return_value.get.return_value = {
            "temperature_schedule": 52.0,
            "temperature_solar": 62.0,
            "temperature_force": 50.0,
            "schedule_start": 23,
            "schedule_stop": 2,
            "solar_threshold": 15.0,
        }

        forecast_mock = mocker.Mock()
        forecast_mock.get_forecast.return_value.get.return_value = ("2022-01-04", 18.2)

        temp_mock = mocker.Mock()
        temp_mock.get_temperature.return_value.get.return_value = 55.0

        db_mock = mocker.Mock()
        db_mock.get_history.return_value.get.return_value = [MetricPoint(1700000000, 55.0, 1)]

        sf = SettingsFile(tmp_path / "settings.ini")
        service = BackendService(
            wattpilot_mock,
            forecast_mock,
            temp_mock,
            database=db_mock,
            load_names={1: "load_1"},
            settings_file=sf,
        )

        snapshot = await service.snapshot()
        assert snapshot.ok
        assert len(snapshot.history) == 1
        assert snapshot.history[0].temperature == 55.0
        assert snapshot.solar_forecast == 18.2
        assert snapshot.forecast_date == "2022-01-04"
        assert snapshot.temperature_schedule == 52.0
        assert snapshot.temperature_solar == 62.0
        assert snapshot.temperature_force == 50.0
        assert snapshot.schedule_start == 23
        assert snapshot.schedule_stop == 2
        assert snapshot.solar_threshold == 15.0

        ok = await service.set_settings(
            temperature_schedule=55.5,
            temperature_solar=64.0,
            temperature_force=48.0,
            schedule_start=1,
            schedule_stop=5,
            solar_threshold=20.0,
        )
        assert ok
        wattpilot_mock.set_settings.assert_called_once_with(
            temperature_schedule=55.5,
            temperature_solar=64.0,
            temperature_force=48.0,
            schedule_start=1,
            schedule_stop=5,
            solar_threshold=20.0,
        )
        saved = sf.load()
        assert saved["temperature_schedule"] == 55.5
        assert saved["schedule_start"] == 1
        assert saved["schedule_stop"] == 5
        assert saved["solar_threshold"] == 20.0


class TestControlPageSettingsSync:
    def test_sync_does_not_mark_dirty_and_accepts_updates(self, mocker):
        store = mocker.Mock()
        store.snapshot = Snapshot(
            ok=True,
            state="idle",
            loads=[],
            temperature=50.0,
            schedule_trigger=False,
            solar_forecast=15.0,
            forecast_date="2022-01-04",
            will_run=False,
            temperature_schedule=52.0,
            temperature_solar=61.0,
            temperature_force=48.0,
            schedule_start=22,
            schedule_stop=4,
            solar_threshold=15.0,
        )

        page = ControlPage(store)
        page.render()
        page.update()

        # Programmatic sync must not leave the page in dirty state
        assert not getattr(page, "_ControlPage__dirty")
        assert getattr(page, "_ControlPage__temp_schedule_slider").value == 52.0
        assert getattr(page, "_ControlPage__solar_threshold_slider").value == 15.0

        # Subsequent backend update while clean should update sliders
        store.snapshot = Snapshot(
            ok=True,
            state="idle",
            loads=[],
            temperature=50.0,
            schedule_trigger=False,
            solar_forecast=18.0,
            forecast_date="2022-01-04",
            will_run=False,
            temperature_schedule=56.0,
            temperature_solar=63.0,
            temperature_force=50.0,
            schedule_start=1,
            schedule_stop=5,
            solar_threshold=22.5,
        )
        page.update()

        assert not getattr(page, "_ControlPage__dirty")
        assert getattr(page, "_ControlPage__temp_schedule_slider").value == 56.0
        assert getattr(page, "_ControlPage__solar_threshold_slider").value == 22.5

        # User modifying a slider sets dirty=True
        getattr(page, "_ControlPage__temp_schedule_slider").value = 58.0
        assert getattr(page, "_ControlPage__dirty")

        # When dirty, subsequent snapshots must not overwrite user changes
        store.snapshot = Snapshot(
            ok=True,
            state="idle",
            loads=[],
            temperature=50.0,
            schedule_trigger=False,
            solar_forecast=15.0,
            forecast_date="2022-01-04",
            will_run=False,
            temperature_schedule=50.0,
            temperature_solar=60.0,
            temperature_force=50.0,
            schedule_start=2,
            schedule_stop=6,
            solar_threshold=15.0,
        )
        page.update()
        assert getattr(page, "_ControlPage__temp_schedule_slider").value == 58.0


class TestHistoryChart:
    def test_build_options_stepped_area(self):
        history = [
            MetricPoint(1700000000, 50.0, 0),
            MetricPoint(1700000060, 52.0, 3),
            MetricPoint(1700000120, 54.0, 3),
            MetricPoint(1700000180, 55.0, 0),
        ]
        options = getattr(HistoryChart, "_HistoryChart__build_options")(history, 3, 1)

        # 2 series: loads and temperature
        assert len(options["series"]) == 2
        loads_series = options["series"][0]
        temp_series = options["series"][1]

        # Loads should be a stepped area line chart (no gaps between consecutive active periods)
        assert loads_series["type"] == "line"
        assert loads_series["step"] == "end"
        assert "areaStyle" in loads_series
        assert loads_series["showSymbol"] is False

        # Temperature should be a line chart on left y-axis
        assert temp_series["type"] == "line"
        assert temp_series["yAxisIndex"] == 0

        # Legend icon for loads should be roundRect
        legend_data = options["legend"]["data"]
        assert any(isinstance(item, dict) and item.get("icon") == "roundRect" for item in legend_data)

    def test_outage_closes_active_load(self):
        # When an active load has a gap > 120s between samples, an intermediate drop to 0 is inserted after 60s
        history = [
            MetricPoint(1700000000, 50.0, 3),
            MetricPoint(1700000300, 50.0, 0),  # 300s gap (>120s)
        ]
        options = getattr(HistoryChart, "_HistoryChart__build_options")(history, 3, 1)
        loads_data = options["series"][0]["data"]
        # Expected: (1700000000*1000, 3), ((1700000000+60)*1000, 0), (1700000300*1000, 0)
        assert [1700000060000, 0] in loads_data

    def test_recent_sample_extends_to_now(self):
        now = int(datetime.now(tz=UTC).timestamp())
        history = [
            MetricPoint(now - 30, 55.0, 2),
        ]
        options = getattr(HistoryChart, "_HistoryChart__build_options")(history, 3, 1)
        loads_data = options["series"][0]["data"]
        # There should be a point extending close to current time with value 2
        assert len(loads_data) == 2
        assert loads_data[-1][1] == 2
        assert loads_data[-1][0] >= (now - 30) * 1000

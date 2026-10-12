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
import logging
import os
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS_FILE: Final[str] = "config.ini.settings"
TEMP_MIN: Final[float] = 45.0
TEMP_MAX: Final[float] = 65.0
TEMP_STEP: Final[float] = 0.5


def in_schedule_window(hour: int, start: int, stop: int) -> bool:
    """Check whether a given hour (0..23) is within the scheduled window [start, stop).

    Supports wrap-around across midnight (e.g. start=23, stop=2).
    If start == stop, the window is empty (returns False).
    """
    if start == stop:
        return False
    if start < stop:
        return start <= hour < stop
    # start > stop: wraps across midnight
    return hour >= start or hour < stop


def get_schedule_duration(start: int, stop: int) -> int:
    """Return the duration of the scheduled window in hours (0..23)."""
    if start == stop:
        return 0
    return (stop - start) % 24


def validate_temperature(value: float | int, name: str = "temperature") -> float:
    """Validate temperature value is between TEMP_MIN and TEMP_MAX in 0.5 steps."""
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}")
    fval = float(value)
    if fval < TEMP_MIN or fval > TEMP_MAX:
        raise ValueError(f"{name} must be between {TEMP_MIN}°C and {TEMP_MAX}°C, got {fval}")
    if abs(round(fval * 2) - fval * 2) > 1e-6:
        raise ValueError(f"{name} must be a multiple of {TEMP_STEP}°C, got {fval}")
    return fval


def validate_hour(value: int, name: str = "hour") -> int:
    """Validate hour is an integer between 0 and 23."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer, got {type(value).__name__}")
    if value < 0 or value > 23:
        raise ValueError(f"{name} must be between 0 and 23, got {value}")
    return value


def validate_settings(
    temperature_schedule: float | int,
    temperature_solar: float | int,
    temperature_force: float | int,
    schedule_start: int,
    schedule_stop: int,
) -> None:
    """Validate all configurable settings."""
    validate_temperature(temperature_schedule, "temperature_schedule")
    validate_temperature(temperature_solar, "temperature_solar")
    validate_temperature(temperature_force, "temperature_force")
    start = validate_hour(schedule_start, "schedule_start")
    stop = validate_hour(schedule_stop, "schedule_stop")
    if start == stop:
        raise ValueError("schedule_start and schedule_stop cannot be equal")


class SettingsFile:
    """Manages reading and writing persistent settings to a dedicated .ini file."""

    def __init__(self, path: str | Path | None = None) -> None:
        raw_path = path or os.environ.get("WATTPILOT_SETTINGS", DEFAULT_SETTINGS_FILE)
        self.__path = Path(raw_path).expanduser().resolve()

    @property
    def path(self) -> Path:
        return self.__path

    def load(self) -> dict[str, Any]:
        """Read existing settings from the ini file if present."""
        if not self.__path.is_file():
            return {}

        parser = configparser.ConfigParser()
        try:
            parser.read(self.__path, encoding="utf-8")
        except Exception:
            logger.exception("Failed to read settings file %s", self.__path)
            return {}

        settings: dict[str, Any] = {}
        if parser.has_option("main", "schedule_start"):
            settings["schedule_start"] = parser.getint("main", "schedule_start")
        if parser.has_option("main", "schedule_stop"):
            settings["schedule_stop"] = parser.getint("main", "schedule_stop")

        for key in ("temperature_schedule", "temperature_solar", "temperature_force"):
            if parser.has_option("temperature", key):
                settings[key] = parser.getfloat("temperature", key)

        return settings

    def save(self, settings: dict[str, Any]) -> None:
        """Atomically persist settings into the ini file."""
        parser = configparser.ConfigParser()
        if self.__path.is_file():
            try:
                parser.read(self.__path, encoding="utf-8")
            except Exception:
                logger.warning("Could not parse existing %s, recreating", self.__path)

        if "main" not in parser:
            parser["main"] = {}
        if "temperature" not in parser:
            parser["temperature"] = {}

        if "schedule_start" in settings:
            parser["main"]["schedule_start"] = str(int(settings["schedule_start"]))
        if "schedule_stop" in settings:
            parser["main"]["schedule_stop"] = str(int(settings["schedule_stop"]))

        for key in ("temperature_schedule", "temperature_solar", "temperature_force"):
            if key in settings:
                parser["temperature"][key] = f"{float(settings[key]):.1f}"

        self.__path.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.__path.with_name(f".{self.__path.name}.tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            parser.write(f)
        os.replace(tmp_file, self.__path)
        logger.info("Saved settings to %s", self.__path)

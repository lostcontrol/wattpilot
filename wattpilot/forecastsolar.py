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
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any

from .actor import WattPilotActor


class ForecastSolar(WattPilotActor):
    DEFAULT_DELAY: float = 14400  # 4 hours

    def __init__(self, config: configparser.ConfigParser) -> None:
        super().__init__()

        self.logger = logging.getLogger(__name__)

        latitude = config.get("forecastsolar", "latitude")
        longitude = config.get("forecastsolar", "longitude")
        declination = config.get("forecastsolar", "declination")
        azimuth = config.get("forecastsolar", "azimuth")
        kwp = config.get("forecastsolar", "kwp")
        self.__schedule_start: int = config.getint("main", "schedule_start")

        self.__host = "api.forecast.solar"
        self.__url = f"https://{self.__host}/estimate/{latitude}/{longitude}/{declination}/{azimuth}/{kwp}"
        self.__watt_hours_day: dict[str, int] = {}
        self.__last_updated: datetime | None = None

    def download(self) -> str:
        headers = {"User-Agent": "Wattpilot"}
        req = urllib.request.Request(self.__url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as f:
            return f.read().decode("utf-8")

    def __get_now(self) -> datetime:
        return datetime.now().astimezone()

    def __get_target_date(self, now: datetime) -> str:
        """Return the target date to evaluate.

        Before 12:00, evaluates today's solar forecast (e.g. post-midnight off-peak window).
        At or after 12:00, evaluates tomorrow's solar forecast (e.g. pre-midnight off-peak window).
        """
        if now.hour < 12:
            return now.strftime("%Y-%m-%d")
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")

    def __compute_next_delay(self, now: datetime, default_delay: float | int) -> float:
        """Compute delay until next run, targeting 15 minutes before schedule_start."""
        base_today = now.replace(minute=0, second=0, microsecond=0)
        target = base_today.replace(hour=self.__schedule_start) - timedelta(minutes=15)
        if target <= now + timedelta(seconds=60):
            target += timedelta(days=1)
        time_to_optimal = max(60.0, (target - now).total_seconds())
        return min(float(default_delay), time_to_optimal)

    def run(self, delay: float | int = DEFAULT_DELAY) -> None:
        self.run_internal(delay)

    def run_internal(self, delay: float | int) -> None:
        next_delay = float(delay)
        try:
            document = json.loads(self.download())
            result = document.get("result", {})
            wh_day: dict[str, Any] = result.get("watt_hours_day", {})
            self.__watt_hours_day = {date_str: int(wh) for date_str, wh in wh_day.items()}
            self.__last_updated = self.__get_now()

            target_date = self.__get_target_date(self.__last_updated)
            wh = self.__watt_hours_day.get(target_date)
            kwh = round(wh / 1000.0, 1) if wh is not None else None
            self.logger.info(
                "Forecast.Solar updated: %s -> %s kWh (all: %s)",
                target_date,
                f"{kwh:.1f}" if kwh is not None else "n/a",
                self.__watt_hours_day,
            )
        except TimeoutError:
            self.logger.error("Timeout connecting to %s", self.__host)
        except urllib.error.URLError as exception:
            self.logger.error("Unable to download data: %s", str(exception.reason))
        except Exception:
            self.logger.exception("Failed to parse Forecast.Solar response")
        finally:
            now = self.__get_now()
            next_delay = self.__compute_next_delay(now, delay)
            self.do_delay(next_delay, "run_internal", args=[delay])

    def get_forecast(self) -> tuple[str | None, float | None]:
        """Return (target_date, kwh) for the upcoming solar day, or (None, None)."""
        now = self.__get_now()
        target_date = self.__get_target_date(now)
        wh = self.__watt_hours_day.get(target_date)
        if wh is not None:
            return target_date, round(wh / 1000.0, 1)
        return None, None

    def get_production(self) -> float:
        """Return forecasted production in kWh for target date, or 0.0 if unavailable."""
        now = self.__get_now()
        target_date = self.__get_target_date(now)
        wh = self.__watt_hours_day.get(target_date)
        if wh is not None:
            return float(wh) / 1000.0
        return 0.0

    def get_url(self) -> str:
        return self.__url

    def set_schedule_start(self, schedule_start: int) -> None:
        self.__schedule_start = int(schedule_start)

    def compute_next_delay(self, now: datetime, default_delay: float | int = DEFAULT_DELAY) -> float:
        return self.__compute_next_delay(now, default_delay)

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

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pykka

from wattpilot.openweathermap import OpenWeatherMap
from wattpilot.temperature import Temperature
from wattpilot.wattpilot import WattPilot

SETTABLE_STATES = ("halt", "idle", "force")
FUTURE_TIMEOUT = 5.0  # seconds to wait for an actor answer


@dataclass
class Snapshot:
    ok: bool = False
    state: str = "-"
    temperature: float | None = None
    loads: list[str] = field(default_factory=list)
    all_loads: list[str] = field(default_factory=list)
    schedule_trigger: bool = False
    cloudiness: int | None = None
    forecast_time: datetime | None = None
    will_run: bool = False


class BackendService:
    """Async facade over the pykka actors."""

    def __init__(
        self,
        wattpilot: pykka.ActorProxy[WattPilot],
        weather: pykka.ActorProxy[OpenWeatherMap],
        temperature: pykka.ActorProxy[Temperature],
        load_names: dict[int, str] | None = None,
    ) -> None:
        self.__wattpilot = wattpilot
        self.__weather = weather
        self.__temperature = temperature
        self.__load_names = load_names or {}
        self.__logger = logging.getLogger(__name__)
        self.__failing = False

    async def snapshot(self) -> Snapshot:
        try:
            result = await asyncio.to_thread(self.__read_snapshot)
            self.__failing = False
            return result
        except Exception:
            if not self.__failing:
                self.__logger.exception("Unable to read the backend state")
            self.__failing = True
            return Snapshot()

    async def set_state(self, state: str) -> bool:
        return await asyncio.to_thread(self.__apply_state, state)

    async def set_schedule_trigger(self, value: bool) -> None:
        await asyncio.to_thread(self.__apply_trigger, value)

    def __read_snapshot(self) -> Snapshot:
        # Request all actor operations up front to obtain their Futures concurrently.
        forecast = self.__weather.get_forecast()
        state = self.__wattpilot.state
        temperature = self.__temperature.get_temperature()
        loads = self.__wattpilot.get_active_loads()
        trigger = self.__wattpilot.get_schedule_trigger()
        will_run = self.__wattpilot.get_scheduled_by_weather()

        # Collect results with timeouts so blocked actors do not hang the worker thread.
        timestamp, cloudiness = forecast.get(timeout=FUTURE_TIMEOUT)
        active_pins = [load.pin for load in loads.get(timeout=FUTURE_TIMEOUT)]
        active_names = [self.__load_names.get(pin, str(pin)) for pin in active_pins]
        all_configured = sorted(set(self.__load_names.values()))
        return Snapshot(
            ok=True,
            state=state.get(timeout=FUTURE_TIMEOUT),
            temperature=round(temperature.get(timeout=FUTURE_TIMEOUT), 1),
            loads=sorted(active_names),
            all_loads=all_configured,
            schedule_trigger=trigger.get(timeout=FUTURE_TIMEOUT),
            cloudiness=cloudiness,
            forecast_time=datetime.fromtimestamp(timestamp, tz=UTC) if timestamp else None,
            will_run=will_run.get(timeout=FUTURE_TIMEOUT),
        )

    def __apply_trigger(self, value: bool) -> None:
        assert isinstance(value, bool)
        self.__wattpilot.set_schedule_trigger(value).get(timeout=FUTURE_TIMEOUT)

    def __apply_state(self, state: str) -> bool:
        if state not in SETTABLE_STATES:
            raise ValueError(state)
        future = getattr(self.__wattpilot, state)()
        return bool(future.get(timeout=FUTURE_TIMEOUT))

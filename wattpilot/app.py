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

from datetime import UTC, datetime
from typing import Any

import pykka

from .openweathermap import OpenWeatherMap
from .temperature import Temperature
from .wattpilot import WattPilot


class WattPilotApp:
    wattpilot: pykka.ActorProxy[WattPilot] | None = None
    openweathermap: pykka.ActorProxy[OpenWeatherMap] | None = None
    temperature: pykka.ActorProxy[Temperature] | None = None

    @staticmethod
    def get_current_state() -> dict[str, Any]:
        assert WattPilotApp.wattpilot is not None
        return {"state": WattPilotApp.wattpilot.state.get()}

    @staticmethod
    def set_current_state(state: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
        assert WattPilotApp.wattpilot is not None
        result = False
        if state["state"] == "halt":
            result = WattPilotApp.wattpilot.halt().get()
        elif state["state"] == "idle":
            result = WattPilotApp.wattpilot.idle().get()
        elif state["state"] == "force":
            result = WattPilotApp.wattpilot.force().get()
        else:
            return "Invalid state", 405
        return {} if result else ("Unable to change state", 406)

    @staticmethod
    def get_schedule_trigger() -> dict[str, bool]:
        assert WattPilotApp.wattpilot is not None
        return {"trigger": WattPilotApp.wattpilot.get_schedule_trigger().get()}

    @staticmethod
    def set_schedule_trigger(trigger: dict[str, bool]) -> Any:
        assert WattPilotApp.wattpilot is not None
        return WattPilotApp.wattpilot.set_schedule_trigger(trigger["trigger"]).get()

    @staticmethod
    def get_weather_forecast() -> dict[str, Any]:
        assert WattPilotApp.openweathermap is not None
        assert WattPilotApp.wattpilot is not None
        timestamp, cloudiness = WattPilotApp.openweathermap.get_forecast().get()
        will_run = WattPilotApp.wattpilot.get_scheduled_by_weather().get()
        return {"timestamp": datetime.fromtimestamp(timestamp, tz=UTC), "cloudiness": cloudiness, "will_run": will_run}

    @staticmethod
    def get_loads() -> list[dict[str, Any]]:
        assert WattPilotApp.wattpilot is not None
        loads = WattPilotApp.wattpilot.get_active_loads().get()
        return [{"pin": load.pin, "state": True} for load in loads]

    @staticmethod
    def get_temperature() -> dict[str, float]:
        assert WattPilotApp.temperature is not None
        return {"temperature": round(WattPilotApp.temperature.get_temperature().get(), 1)}

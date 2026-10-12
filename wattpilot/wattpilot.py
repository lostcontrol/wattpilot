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
import copy
import logging
from datetime import UTC, datetime
from typing import Final

import pykka

from .actor import WattPilotActor, WattPilotModel
from .device import Gpio
from .fronius import Fronius
from .openweathermap import OpenWeatherMap
from .temperature import Temperature


class Load:
    def __init__(self, gpio: Gpio, pin: int) -> None:
        self.__pin: int = pin
        self.__gpio: Gpio = gpio
        self.power: int = 0
        gpio.setup(pin)

    @property
    def pin(self) -> int:
        return self.__pin

    def set_pin(self, value: bool) -> None:
        self.__gpio.set_pin(self.__pin, value)

    def get_pin(self) -> bool:
        return self.__gpio.get_pin(self.__pin)


class AllLoad:
    @staticmethod
    def from_config(config: configparser.ConfigParser, gpio: Gpio) -> AllLoad:
        all_load = AllLoad(gpio)
        sections = [load for load in config.sections() if load.startswith("load_")]
        for section in sorted(sections):
            load = Load(gpio, config.getint(section, "pin"))
            load.power = config.getint(section, "power")
            all_load.get_all_loads().append(load)
        return all_load

    def __init__(self, gpio: Gpio) -> None:
        self.__gpio: Gpio = gpio
        self.__loads: list[Load] = []

    def get_all_loads(self) -> list[Load]:
        return self.__loads

    def get_inactive_loads(self, active_loads: list[Load]) -> list[Load]:
        return [load for load in self.__loads if load not in active_loads]

    def get_minimum_power(self, active_loads: list[Load]) -> int:
        inactive = self.get_inactive_loads(active_loads)
        return min([load.power for load in inactive]) if inactive else 0

    def get_minimum_load(self) -> Load:
        return sorted(self.__loads, key=lambda x: x.power)[0]

    def get_load(self, power: float | int, active_loads: list[Load]) -> Load | None:
        loads: list[Load] = []
        for load in self.get_inactive_loads(active_loads):
            if load.power <= power:
                loads.append(load)
        if loads:
            return sorted(loads, key=lambda x: x.power, reverse=True)[0]
        return None


class WattPilot(WattPilotActor):
    states: Final = [
        "halt",
        "idle",
        "force",
        "schedule",
        "solar",
    ]

    DEFAULT_DELAY: float = 60

    def __init__(
        self,
        config: configparser.ConfigParser,
        power: pykka.ActorProxy[Fronius],
        gpio: Gpio,
        weather: pykka.ActorProxy[OpenWeatherMap],
        temperature: pykka.ActorProxy[Temperature],
    ) -> None:
        super().__init__()

        self.logger = logging.getLogger(__name__)

        # Initialize the state machine
        self.__machine = WattPilotModel(model=self, states=WattPilot.states, initial="halt")

        # Transitions
        self.__machine.add_transition("halt", "*", "halt")
        self.__machine.add_transition(
            "idle",
            [
                "halt",
                "solar",
                "schedule",
                "force",
            ],
            "idle",
            after=self.after_idle_power,
        )
        self.__machine.add_transition("update_power", "idle", None, after=self.after_idle_power)
        self.__machine.add_transition(
            "force",
            [
                "idle",
                "schedule",
                "solar",
            ],
            "force",
            after=self.after_force,
        )
        self.__machine.add_transition("force", "force", None, after=self.after_force)
        self.__machine.add_transition("update_force", "force", None, after=self.after_force)
        self.__machine.add_transition("schedule", "idle", "schedule", after=self.after_schedule)
        self.__machine.add_transition("schedule", "schedule", None, after=self.after_schedule)
        self.__machine.add_transition("solar", "idle", "solar")
        self.__machine.add_transition("update_power", "solar", None, after=self.after_solar_power)

        self.__loads: AllLoad = AllLoad.from_config(config, gpio)
        self.__active_loads: list[Load] = []
        self.__power: pykka.ActorProxy[Fronius] = power
        self.__weather: pykka.ActorProxy[OpenWeatherMap] = weather
        self.__temperature: pykka.ActorProxy[Temperature] = temperature

        self.__hysteresis_to_grid: int = config.getint("main", "hysteresis_to_grid")
        self.__hysteresis_from_grid: int = config.getint("main", "hysteresis_from_grid")
        self.__schedule_trigger: bool = False
        self.__schedule_start: int = config.getint("main", "schedule_start")
        self.__schedule_stop: int = config.getint("main", "schedule_stop")
        self.__cloudiness_level: int = config.getint("main", "cloudiness_level")
        self.__temperature_schedule: int = config.getint("temperature", "temperature_schedule")
        self.__temperature_solar: int = config.getint("temperature", "temperature_solar")
        self.__temperature_force: int = config.getint("temperature", "temperature_force")

    def get_active_loads(self) -> list[Load]:
        return copy.deepcopy(self.__active_loads)

    def __stop_all_active(self) -> None:
        for load in self.__active_loads:
            load.set_pin(False)
        self.__active_loads = []

    def __start_all_inactive(self) -> None:
        for load in self.__loads.get_inactive_loads(self.__active_loads):
            load.set_pin(True)
            self.__active_loads.append(load)

    def on_enter_halt(self) -> None:
        self.logger.info("Entering halt state")
        self.__stop_all_active()
        self.__power.do_cancel.defer()
        self.__weather.do_cancel.defer()

    def on_exit_halt(self) -> None:
        self.__weather.run.defer(3600)

    def on_enter_idle(self) -> None:
        self.logger.info("Entering idle state")
        self.__stop_all_active()
        self.__power.register_callback(self._proxy.update_power).get()
        self.__power.run.defer(60)

    def get_scheduled_by_weather(self) -> bool:
        return self.__weather.get_cloudiness().get() > self.__cloudiness_level

    def check_temperature_min(self, limit: float | int, hysteresis: float | int = 1) -> bool:
        temperature = self.__temperature.get_temperature().get()
        check = temperature < limit - hysteresis
        if check:
            self.logger.info("Temperature low: %.2f", temperature)
        return check

    def check_temperature_max(self, limit: float | int, hysteresis: float | int = 0.5) -> bool:
        temperature = self.__temperature.get_temperature().get()
        check = temperature > limit + hysteresis
        if check:
            self.logger.info("Temperature high: %.2f", temperature)
        return check

    def after_idle_power(self) -> None:
        minimum_power = self.__loads.get_minimum_power(self.__active_loads)
        if minimum_power + self.__hysteresis_to_grid <= -self.__power.get_power().get():
            if self.check_temperature_min(self.__temperature_solar):
                self.do_delay(0, "solar")
        elif self.__schedule_start <= datetime.now(tz=UTC).hour < self.__schedule_stop:
            if self.__schedule_trigger or self.get_scheduled_by_weather():
                if self.check_temperature_min(self.__temperature_schedule):
                    self.do_delay(0, "schedule")

    def on_exit_idle(self) -> None:
        self.logger.info("Exiting idle state")
        self.__power.do_cancel.defer()
        self.__power.register_callback(None).get()

    def get_schedule_trigger(self) -> bool:
        return self.__schedule_trigger

    def set_schedule_trigger(self, value: bool) -> None:
        assert isinstance(value, bool)
        self.logger.info("Schedule trigger has been %sable", "en" if value else "dis")
        self.__schedule_trigger = value

    def on_enter_schedule(self) -> None:
        self.logger.info("Entering schedule state")
        self.__schedule_trigger = False
        self.__start_all_inactive()

    def after_schedule(self) -> None:
        if datetime.now(tz=UTC).hour >= self.__schedule_stop:
            self.do_delay(0, "idle")
        elif self.check_temperature_max(self.__temperature_schedule):
            self.do_delay(0, "idle")
        else:
            self.do_delay(self.DEFAULT_DELAY, "schedule")

    def on_enter_force(self) -> None:
        self.logger.info("Entering force state")
        if not self.check_temperature_max(self.__temperature_force):
            self.__start_all_inactive()

    def after_force(self) -> None:
        if self.check_temperature_max(self.__temperature_force):
            if self.__active_loads:
                self.logger.info("Force: temperature limit reached, stopping loads")
                self.__stop_all_active()
        elif self.check_temperature_min(self.__temperature_force):
            if self.__loads.get_inactive_loads(self.__active_loads):
                self.logger.info("Force: temperature below threshold, starting all loads")
                self.__start_all_inactive()
        self.do_delay(self.DEFAULT_DELAY, "update_force")

    def on_enter_solar(self) -> None:
        self.logger.info("Entering solar state")
        self.__power.register_callback(self._proxy.update_power).get()
        self.__power.run.defer(30)

    def after_solar_power(self) -> None:
        power = self.__power.get_power().get()
        if self.check_temperature_max(self.__temperature_solar):
            self.do_delay(0, "idle")
        elif power > self.__hysteresis_from_grid:
            if not self.__active_loads:
                self.do_delay(0, "idle")
            else:
                self.logger.info("Turning a load off, power consumption at %dW", power)
                load = self.__active_loads.pop()
                load.set_pin(False)
        else:
            load = self.__loads.get_load(-power - self.__hysteresis_to_grid, self.__active_loads)
            if load is not None:
                self.logger.info("Turning a load on, power generation at %dW", -power)
                self.__active_loads.append(load)
                load.set_pin(True)

    def on_exit_solar(self) -> None:
        self.logger.info("Exiting solar state")
        self.__power.do_cancel.defer()
        self.__power.register_callback(None).get()

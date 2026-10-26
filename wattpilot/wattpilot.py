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
from datetime import datetime
from typing import Final

import pykka

from .actor import WattPilotActor, WattPilotModel
from .database import Database
from .device import Gpio
from .forecastsolar import ForecastSolar
from .fronius import Fronius
from .settings import in_schedule_window, validate_settings
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
        forecast: pykka.ActorProxy[ForecastSolar],
        temperature: pykka.ActorProxy[Temperature],
        database: pykka.ActorProxy[Database] | None = None,
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
        self.__forecast: pykka.ActorProxy[ForecastSolar] = forecast
        self.__temperature: pykka.ActorProxy[Temperature] = temperature
        self.__database: pykka.ActorProxy[Database] | None = database

        self.__hysteresis_to_grid: int = config.getint("main", "hysteresis_to_grid")
        self.__hysteresis_from_grid: int = config.getint("main", "hysteresis_from_grid")
        self.__schedule_trigger: bool = False
        self.__schedule_start: int = config.getint("main", "schedule_start")
        self.__schedule_stop: int = config.getint("main", "schedule_stop")
        self.__solar_threshold: float = config.getfloat("main", "solar_threshold")
        self.__temperature_schedule: float = config.getfloat("temperature", "temperature_schedule")
        self.__temperature_solar: float = config.getfloat("temperature", "temperature_solar")
        self.__temperature_force: float = config.getfloat("temperature", "temperature_force")

    def __get_now(self) -> datetime:
        return datetime.now().astimezone()

    def get_settings(self) -> dict[str, float | int]:
        return {
            "temperature_schedule": self.__temperature_schedule,
            "temperature_solar": self.__temperature_solar,
            "temperature_force": self.__temperature_force,
            "schedule_start": self.__schedule_start,
            "schedule_stop": self.__schedule_stop,
            "solar_threshold": self.__solar_threshold,
        }

    def set_settings(
        self,
        temperature_schedule: float | int,
        temperature_solar: float | int,
        temperature_force: float | int,
        schedule_start: int,
        schedule_stop: int,
        solar_threshold: float | int,
    ) -> None:
        validate_settings(
            temperature_schedule=temperature_schedule,
            temperature_solar=temperature_solar,
            temperature_force=temperature_force,
            schedule_start=schedule_start,
            schedule_stop=schedule_stop,
            solar_threshold=solar_threshold,
        )
        self.logger.info(
            "Updating settings: schedule=%.1f°C, solar=%.1f°C, force=%.1f°C, period=%d..%d, solar_threshold=%.1f kWh",
            temperature_schedule,
            temperature_solar,
            temperature_force,
            schedule_start,
            schedule_stop,
            solar_threshold,
        )
        self.__temperature_schedule = float(temperature_schedule)
        self.__temperature_solar = float(temperature_solar)
        self.__temperature_force = float(temperature_force)
        self.__schedule_start = int(schedule_start)
        self.__schedule_stop = int(schedule_stop)
        self.__solar_threshold = float(solar_threshold)
        self.__forecast.set_schedule_start(self.__schedule_start).get()

    def get_state(self) -> str:
        return str(getattr(self, "state"))

    def get_active_loads(self) -> list[Load]:
        return copy.deepcopy(self.__active_loads)

    def record_metrics(self) -> None:
        if self.__database is not None:
            try:
                temp = self.__temperature.get_temperature().get()
                self.__database.record(temp, len(self.__active_loads))
            except Exception:
                self.logger.exception("Failed to record metrics into database")

    def __stop_all_active(self) -> None:
        had_active = bool(self.__active_loads)
        for load in self.__active_loads:
            load.set_pin(False)
        self.__active_loads = []
        if had_active:
            self.record_metrics()

    def __start_all_inactive(self) -> None:
        added = False
        for load in self.__loads.get_inactive_loads(self.__active_loads):
            load.set_pin(True)
            self.__active_loads.append(load)
            added = True
        if added:
            self.record_metrics()

    def on_enter_halt(self) -> None:
        self.logger.info("Entering halt state")
        self.__stop_all_active()
        self.__power.do_cancel.defer()
        self.__forecast.do_cancel.defer()

    def on_exit_halt(self) -> None:
        self.__forecast.run.defer(ForecastSolar.DEFAULT_DELAY)

    def on_enter_idle(self) -> None:
        self.logger.info("Entering idle state")
        self.__stop_all_active()
        self.__power.register_callback(self.get_proxy().update_power).get()
        self.__power.run.defer(60)

    def get_scheduled_by_forecast(self) -> bool:
        return self.__forecast.get_production().get() < self.__solar_threshold

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
        elif in_schedule_window(self.__get_now().hour, self.__schedule_start, self.__schedule_stop):
            if self.__schedule_trigger or self.get_scheduled_by_forecast():
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
        if not in_schedule_window(self.__get_now().hour, self.__schedule_start, self.__schedule_stop):
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
        self.__power.register_callback(self.get_proxy().update_power).get()
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
                self.record_metrics()
        else:
            load = self.__loads.get_load(-power - self.__hysteresis_to_grid, self.__active_loads)
            if load is not None:
                self.logger.info("Turning a load on, power generation at %dW", -power)
                self.__active_loads.append(load)
                load.set_pin(True)
                self.record_metrics()

    def on_exit_solar(self) -> None:
        self.logger.info("Exiting solar state")
        self.__power.do_cancel.defer()
        self.__power.register_callback(None).get()


class MetricPoller(WattPilotActor):
    """Dedicated polling actor that periodically samples temperature and loads into the database."""

    DEFAULT_DELAY: float = 60

    def __init__(
        self,
        database: pykka.ActorProxy[Database],
        temperature: pykka.ActorProxy[Temperature],
        wattpilot: pykka.ActorProxy[WattPilot],
    ) -> None:
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.__database: pykka.ActorProxy[Database] = database
        self.__temperature: pykka.ActorProxy[Temperature] = temperature
        self.__wattpilot: pykka.ActorProxy[WattPilot] = wattpilot

    def run(self, delay: float | int = DEFAULT_DELAY) -> None:
        self.run_internal(delay)

    def run_internal(self, delay: float | int) -> None:
        try:
            temp = self.__temperature.get_temperature().get()
            active_loads = len(self.__wattpilot.get_active_loads().get())
            self.__database.record(temp, active_loads)
            self.logger.debug("Polled metrics: temp=%.1f loads=%d", temp, active_loads)
        except Exception:
            self.logger.exception("Failed to poll metrics")
        finally:
            self.do_delay(delay, "run_internal", args=[delay])

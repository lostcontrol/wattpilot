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
import time

from freezegun import freeze_time
import pykka
import pytest

from wattpilot.wattpilot import WattPilot


@pytest.fixture
def power(mocker):
    return mocker.Mock()


@pytest.fixture
def gpio(mocker):
    return mocker.Mock()


@pytest.fixture
def weather(mocker):
    return mocker.Mock()


@pytest.fixture
def config():
    ini = """
        [main]
        hysteresis_to_grid = 200
        hysteresis_from_grid = 0
        schedule_start = 2
        schedule_stop = 6

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


@pytest.fixture
def wattpilot(mocker, config, power, gpio, weather):
    WattPilot.DEFAULT_DELAY = 0.01
    with freeze_time("1981-05-30 00:00:01"):
        wattpilot = WattPilot.start(config, power, gpio, weather).proxy()
        yield wattpilot
        wattpilot.halt.defer()
        assert wattpilot.is_halt().get()
        pykka.ActorRegistry.stop_all()


def wait_with_timeout(method, timeout=1):
    start = time.time()
    while not method():
        diff = time.time() - start
        if diff > timeout:
            assert False, "Timeout"
        time.sleep(0.01)


class FakeFuture:

    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class PowerFirstThen:
    latch = True

    def __init__(self, first, then):
        self.first = FakeFuture(first)
        self.then = FakeFuture(then)

    def __call__(self):
        if self.latch:
            self.latch = False
            return self.first
        else:
            return self.then


class TestWattPilot:

    def test_idle_not_enough_power(self, mocker, wattpilot, power):
        power.get_power.return_value = FakeFuture(0)
        wattpilot.idle.defer()
        assert wattpilot.is_idle().get()

    def test_idle_enough_power_for_one_load(self, mocker, wattpilot, gpio, power):
        power.get_power.return_value = FakeFuture(-2000)
        wattpilot.idle.defer()
        wattpilot.update_power().get()
        wait_with_timeout(lambda: wattpilot.is_solar().get())
        wattpilot.update_power().get()
        gpio.set_pin.assert_has_calls([mocker.call(1, True)])

    def test_idle_enough_power_for_two_loads(self, mocker, wattpilot, gpio, power):
        power.get_power.return_value = FakeFuture(-3000)
        wattpilot.idle.defer()
        wattpilot.update_power().get()
        wait_with_timeout(lambda: wattpilot.is_solar().get())
        wattpilot.update_power().get()
        wattpilot.update_power().get()
        gpio.set_pin.assert_has_calls([mocker.call(2, True), mocker.call(1, True)])

    def test_enough_power_for_two_loads_then_one(self, mocker, wattpilot, gpio, power):
        power.get_power.return_value = FakeFuture(-3000)
        wattpilot.idle.defer()
        wattpilot.update_power().get()
        wait_with_timeout(lambda: wattpilot.is_solar().get())
        wattpilot.update_power().get()
        wattpilot.update_power().get()
        gpio.set_pin.assert_has_calls([mocker.call(2, True), mocker.call(1, True)])
        gpio.set_pin.reset_mock()
        power.get_power.return_value = FakeFuture(500)
        wattpilot.update_power().get()
        wattpilot.update_power().get()
        gpio.set_pin.assert_has_calls([mocker.call(1, False), mocker.call(2, False)])
        wattpilot.update_power().get()
        wait_with_timeout(lambda: wattpilot.is_idle().get())

    def test_two_loads_then_one_and_two(self, mocker, wattpilot, gpio, power):
        power.get_power.return_value = FakeFuture(-3000)
        wattpilot.idle.defer()
        wattpilot.update_power().get()
        wait_with_timeout(lambda: wattpilot.is_solar().get())
        wattpilot.update_power().get()
        wattpilot.update_power().get()
        gpio.set_pin.assert_has_calls([mocker.call(2, True), mocker.call(1, True)])
        # No more power
        gpio.set_pin.reset_mock()
        power.get_power.return_value = FakeFuture(500)
        wattpilot.update_power().get()
        gpio.set_pin.assert_has_calls([mocker.call(1, False)])
        # Power available again
        gpio.set_pin.reset_mock()
        power.get_power.return_value = FakeFuture(-2000)
        wattpilot.update_power().get()
        gpio.set_pin.assert_has_calls([mocker.call(1, True)])

    def test_force(self, mocker, wattpilot, gpio, power):
        power.get_power.return_value = FakeFuture(0)
        wattpilot.idle.defer()
        wattpilot.force.defer()
        wait_with_timeout(lambda: wattpilot.is_force().get())
        gpio.set_pin.assert_has_calls([mocker.call(1, True), mocker.call(2, True)])

    def test_schedule_no_trigger(self, mocker, wattpilot, gpio, power, weather):
        power.get_power.return_value = FakeFuture(0)
        weather.get_cloudiness.return_value = FakeFuture(0)
        wattpilot.idle.defer()
        wattpilot.set_schedule_trigger(False).get()
        with freeze_time("1981-05-30 02:00:01", tick=True):
            time.sleep(0.1)
            wait_with_timeout(lambda: wattpilot.is_idle().get())
        assert gpio.set_pin.call_count == 0

    def test_schedule_trigger_set(self, mocker, wattpilot, gpio, power, weather):
        power.get_power.return_value = FakeFuture(0)
        weather.get_cloudiness.return_value = FakeFuture(0)
        wattpilot.idle.defer()
        wattpilot.set_schedule_trigger(True).get()
        with freeze_time("1981-05-30 02:00:01", tick=True):
            time.sleep(0.1)
            wait_with_timeout(lambda: wattpilot.is_schedule().get())
        gpio.set_pin.assert_has_calls([mocker.call(1, True), mocker.call(2, True)])

    def test_schedule_start_and_stop(self, mocker, wattpilot, gpio, power):
        power.get_power.return_value = FakeFuture(0)
        wattpilot.idle.defer()
        # Start
        wattpilot.set_schedule_trigger(True).get()
        with freeze_time("1981-05-30 02:00:01", tick=True):
            time.sleep(0.1)
            wait_with_timeout(lambda: wattpilot.is_schedule().get())
        gpio.set_pin.assert_has_calls([mocker.call(1, True), mocker.call(2, True)])
        # Stop
        gpio.set_pin.reset_mock()
        with freeze_time("1981-05-30 06:00:01", tick=True):
            time.sleep(0.1)
            wait_with_timeout(lambda: wattpilot.is_idle().get())
        gpio.set_pin.assert_has_calls([mocker.call(1, False), mocker.call(2, False)])

    def test_schedule_no_trigger_sunny_tomorrow(self, mocker, wattpilot, gpio, power, weather):
        power.get_power.return_value = FakeFuture(0)
        wattpilot.idle.defer()
        wattpilot.set_schedule_trigger(False).get()
        weather.get_cloudiness.return_value = FakeFuture(0)
        with freeze_time("1981-05-30 02:00:01", tick=True):
            time.sleep(0.1)
            wait_with_timeout(lambda: wattpilot.is_idle().get())
        assert gpio.set_pin.call_count == 0

    def test_schedule_no_trigger_not_sunny_tomorrow(self, mocker, wattpilot, gpio, power, weather):
        power.get_power.return_value = FakeFuture(0)
        wattpilot.idle.defer()
        wattpilot.set_schedule_trigger(False).get()
        weather.get_cloudiness.return_value = FakeFuture(100)
        with freeze_time("1981-05-30 02:00:01", tick=True):
            time.sleep(0.1)
            wait_with_timeout(lambda: wattpilot.is_schedule().get())
        gpio.set_pin.assert_has_calls([mocker.call(1, True), mocker.call(2, True)])

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
import os

import pykka
import pytest

from wattpilot.fronius import Fronius


@pytest.fixture
def config():
    ini = """
        [main]
        hysteresis = 200
        schedule_start = 2
        schedule_stop = 6
        fronius_host = fronius

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
def fronius(mocker, config):
    fronius = Fronius.start(config).proxy()
    yield fronius
    pykka.ActorRegistry.stop_all()


class TestFronius:

    @staticmethod
    def __read_json_asset(filename):
        with open(os.path.join("test/assets", f"{filename}.json"), "r") as f:
            return f.read()

    def test_run(self, mocker, fronius):
        mocker.patch.object(Fronius, "download").return_value = self.__read_json_asset("meter01")
        fronius.run_internal(9999).get()
        assert fronius.get_power().get() == 0
        mocker.patch.object(Fronius, "download").return_value = self.__read_json_asset("meter02")
        fronius.run_internal(9999).get()
        assert 400 < fronius.get_power().get() < 500
        mocker.patch.object(Fronius, "download").return_value = self.__read_json_asset("meter02")
        fronius.run_internal(9999).get()
        # We use an average
        assert fronius.get_power().get() > 0

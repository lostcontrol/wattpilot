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

import pykka
import pytest
from freezegun import freeze_time

from test.test_wattpilot import FakeFuture
from wattpilot.pvoutput import PVOutput
from wattpilot.temperature import Temperature


@pytest.fixture
def config():
    ini = """
        [pvoutput]
        key=1234
        sid=5678
        field=v12
    """
    configuration = configparser.ConfigParser()
    configuration.read_string(ini)
    return configuration


@pytest.fixture
def temperature(mocker):
    mock = mocker.Mock(spec=Temperature)
    mock.get_temperature.return_value = FakeFuture(50)
    return mock


@pytest.fixture
def pvoutput(mocker, config, temperature):
    with freeze_time("2020-06-07 06:00:00"):
        actor = PVOutput.start(config, temperature).proxy()
        yield actor
        pykka.ActorRegistry.stop_all()


class TestPVOutput:

    def test_send_temperature(self, mocker, pvoutput):
        def call(url):
            assert url == "https://pvoutput.org/service/r2/addstatus.jsp?key=1234&sid=5678&d=20200607&t=06:00&v12=50"
            return mocker.MagicMock()

        mock = mocker.patch("urllib.request.urlopen")
        mock.side_effect = call
        pvoutput.run().get()
        mock.assert_called_once()

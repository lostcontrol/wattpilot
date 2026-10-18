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

import logging
from datetime import UTC, datetime, timedelta
from threading import Timer
from types import TracebackType
from typing import Any

import pykka

# from transitions.extensions import HierarchicalGraphMachine as Machine
from transitions.extensions import HierarchicalMachine as Machine

logger = logging.getLogger(__name__)


class WattPilotModel(Machine):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("before_state_change", []).extend(["do_cancel", self.__update_state_time])
        super().__init__(auto_transitions=False, ignore_invalid_triggers=True, *args, **kwargs)
        self.__state_time: datetime | None = datetime.now(tz=UTC)

    def __update_state_time(self) -> None:
        self.__state_time = datetime.now(tz=UTC)

    def get_time_in_state(self) -> timedelta:
        if self.__state_time is None:
            return timedelta()
        return datetime.now(tz=UTC) - self.__state_time


class WattPilotActor(pykka.ThreadingActor):
    def __init__(self) -> None:
        super().__init__()
        self.__proxy: Any = self.actor_ref.proxy()
        self.__timer: Timer | None = None

    def get_proxy(self) -> Any:
        return self.__proxy

    def on_failure(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        # The actor is going to die
        logger.fatal(exception_type, exception_value, traceback)

    def on_stop(self) -> None:
        self.do_cancel()

    def get_actor(self, name: str) -> Any | None:
        fsm = pykka.ActorRegistry.get_by_class_name(name)
        if fsm:
            return fsm[0].proxy()
        logger.critical(f"Actor {name} not found!!!")
        return None

    def __do_cancel(self) -> None:
        if self.__timer:
            self.__timer.cancel()
            self.__timer = None

    def do_cancel(self) -> None:
        self.__do_cancel()

    def do_delay(self, delay: float | int, method: str, *args: Any, **kwargs: Any) -> None:
        assert isinstance(method, str)
        assert delay >= 0
        # Stop an already running timer
        self.__do_cancel()
        func = getattr(self.get_proxy(), method)
        if delay > 0:
            self.__timer = Timer(delay, func.defer, *args, **kwargs)
            self.__timer.start()
        else:
            func.defer(*args, **kwargs)

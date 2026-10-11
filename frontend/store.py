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

import asyncio

from .service import BackendService, Snapshot

POLL_SECONDS = 2.0


class SnapshotStore:
    """Holds the latest Snapshot, refreshed by a single background task."""

    def __init__(self, service: BackendService) -> None:
        self.__service = service
        self.__snapshot = Snapshot()
        self.__task: asyncio.Task[None] | None = None

    @property
    def service(self) -> BackendService:
        return self.__service

    @property
    def snapshot(self) -> Snapshot:
        return self.__snapshot

    async def refresh(self) -> None:
        self.__snapshot = await self.__service.snapshot()

    def start(self) -> None:
        self.__task = asyncio.create_task(self.__loop())

    def stop(self) -> None:
        if self.__task:
            self.__task.cancel()

    async def __loop(self) -> None:
        while True:
            await self.refresh()
            await asyncio.sleep(POLL_SECONDS)

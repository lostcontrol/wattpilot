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

from abc import ABC, abstractmethod

from nicegui import ui

from ..layout import Layout
from ..store import POLL_SECONDS, SnapshotStore


class Page(ABC):
    """One instance per browser request. Subclasses own their widgets."""

    path: str
    title: str

    def __init__(self, store: SnapshotStore) -> None:
        self.__store = store
        self.__layout = Layout(self.title, self.path)

    @property
    def store(self) -> SnapshotStore:
        return self.__store

    def build(self) -> None:
        """Template method: frame + content + refresh timer."""
        with self.__layout:
            self.render()
        ui.timer(POLL_SECONDS, self.__tick, immediate=True)

    @abstractmethod
    def render(self) -> None:
        """Create the widgets. Called once per client inside the layout."""

    @abstractmethod
    def update(self) -> None:
        """Copy self.store.snapshot into the widgets. Must not do I/O."""

    def __tick(self) -> None:
        self.update()

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


class AuthPolicy(ABC):
    """Decides whether the current browser client may see a page."""

    @abstractmethod
    def is_allowed(self) -> bool: ...

    def on_denied(self) -> None:
        """Called when is_allowed() is False. Override to redirect to a login page."""


class NoAuth(AuthPolicy):
    def is_allowed(self) -> bool:
        return True

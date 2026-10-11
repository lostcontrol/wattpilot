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
from collections.abc import Callable
from pathlib import Path

from nicegui import app, ui

from .auth import AuthPolicy, NoAuth
from .pages.control import ControlPage
from .pages.dashboard import DashboardPage
from .pages.page import Page
from .store import SnapshotStore


class FrontendApp:
    """Main application orchestrator configuring pages, styles, and lifecycle hooks."""

    PAGES: tuple[type[Page], ...] = (DashboardPage, ControlPage)

    def __init__(
        self,
        store: SnapshotStore,
        cleanup: Callable[[], None],
        auth: AuthPolicy | None = None,
    ) -> None:
        self.__store = store
        self.__cleanup = cleanup
        self.__auth = auth or NoAuth()

    def run(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self.__load_styles()
        self.__register_pages()
        app.on_startup(self.__store.start)
        app.on_shutdown(self.__on_shutdown)
        ui.run(
            host=host,
            port=port,
            title="Wattpilot",
            favicon="⚡",
            reload=False,
            show=False,
            viewport="width=device-width, initial-scale=1",
        )

    def __load_styles(self) -> None:
        static_dir = Path(__file__).parent / "static"
        if static_dir.is_dir():
            app.add_static_files("/static", static_dir)
        css_file = static_dir / "style.css"
        if css_file.is_file():
            ui.add_css(css_file.read_text(encoding="utf-8"), shared=True)

    def __register_pages(self) -> None:
        for page_class in self.PAGES:
            ui.page(page_class.path)(self.__make_handler(page_class))

    def __make_handler(self, page_class: type[Page]) -> Callable[[], None]:
        def handler() -> None:
            ui.colors(
                primary="#4f46e5",
                positive="#22c55e",
                warning="#f97316",
                negative="#ef4444",
            )
            ui.dark_mode(None)
            if not self.__auth.is_allowed():
                self.__auth.on_denied()
                return
            page_class(self.__store).build()

        return handler

    async def __on_shutdown(self) -> None:
        self.__store.stop()
        # Cleanup blocks on actor futures; keep it off the event loop.
        await asyncio.to_thread(self.__cleanup)

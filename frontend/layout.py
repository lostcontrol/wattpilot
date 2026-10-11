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

from nicegui import ui

from .i18n import i18n


class Layout:
    """Mobile-first page frame, used as a context manager."""

    TABS: tuple[tuple[str, str, str], ...] = (
        ("/", "nav.dashboard", "dashboard"),
        ("/control", "nav.control", "tune"),
    )

    def __init__(self, title: str, active_path: str) -> None:
        self.__title = title
        self.__active_path = active_path
        self.__column: ui.column | None = None

    def __enter__(self) -> Layout:
        self.__build_header()
        self.__build_bottom_nav()
        self.__column = ui.column().classes("wp-container")
        self.__column.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        if self.__column:
            self.__column.__exit__(*exc)

    def __build_header(self) -> None:
        with ui.header().classes("wp-header"):
            with ui.row().classes("wp-header-left"):
                ui.label(f"⚡ {i18n.t('app.title')}").classes("wp-brand-title")

            with ui.row().classes("wp-header-right"):
                # Desktop navigation
                with ui.row().classes("wp-nav-desktop"):
                    for path, key, icon in self.TABS:
                        btn = ui.button(i18n.t(key), icon=icon, on_click=lambda p=path: ui.navigate.to(p))
                        if path == self.__active_path:
                            btn.props("no-caps flat unelevated color=primary text-color=primary")
                        else:
                            btn.props("no-caps flat unelevated color=grey text-color=grey-7")

                # Language switcher (EN / FR)
                self.__build_lang_switcher()

    def __build_lang_switcher(self) -> None:
        with ui.row().classes("wp-lang-switcher"):
            for lang_code in ("en", "fr"):
                is_active = i18n.current_lang == lang_code
                btn = ui.button(
                    lang_code.upper(),
                    on_click=lambda c=lang_code: self.__switch_lang(c),
                )
                if is_active:
                    btn.props("dense rounded unelevated color=primary text-color=white size=sm")
                else:
                    btn.props("dense rounded flat color=grey text-color=grey-7 size=sm")

    def __switch_lang(self, lang_code: str) -> None:
        if i18n.current_lang != lang_code:
            i18n.set_lang(lang_code)
            cookie = f"lang={lang_code}; path=/; max-age=31536000; SameSite=Lax"
            ui.run_javascript(f'document.cookie = "{cookie}"; window.location.reload();')

    def __build_bottom_nav(self) -> None:
        with ui.row().classes("wp-nav"):
            for path, key, icon in self.TABS:
                btn = ui.button(i18n.t(key), icon=icon, on_click=lambda p=path: ui.navigate.to(p))
                btn.classes("wp-nav-button")
                if path == self.__active_path:
                    btn.props("no-caps unelevated color=primary text-color=white")
                else:
                    btn.props("no-caps flat color=grey text-color=grey-7")

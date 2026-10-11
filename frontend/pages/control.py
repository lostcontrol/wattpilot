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

from nicegui import ui

from ..components import Card, StateHero
from ..i18n import i18n
from ..store import SnapshotStore
from .page import Page


class ControlPage(Page):
    """Control page allowing manual state transitions (halt, idle, force)."""

    path: str = "/control"
    title: str = "Control"

    MODES: tuple[tuple[str, str, str, str, str], ...] = (
        ("idle", "control.idle", "hourglass_empty", "primary", "control.desc.idle"),
        ("force", "control.force", "bolt", "warning", "control.desc.force"),
        ("halt", "control.halt", "power_settings_new", "grey-7", "control.desc.halt"),
    )

    def __init__(self, store: SnapshotStore) -> None:
        super().__init__(store)
        self.__hero: StateHero | None = None
        self.__dialog: ui.dialog | None = None
        self.__dialog_msg: ui.label | None = None
        self.__dialog_warn: ui.label | None = None
        self.__pending_state: str = ""
        self.__buttons: list[ui.button] = []

    def render(self) -> None:
        self.__hero = StateHero()

        with Card(title_key="control.change_mode", icon="tune"):
            ui.label(i18n.t("control.desc.main")).classes("wp-subtext")

            with ui.column().classes("w-full gap-3 mt-2"):
                for state, name_key, icon, color, desc_key in self.MODES:
                    btn = (
                        ui.button(
                            on_click=lambda s=state: self.__request_state(s),
                        )
                        .props(f"no-caps unelevated color={color} size=lg")
                        .classes("wp-mode-button")
                    )
                    with btn:
                        with ui.row().classes("wp-mode-row"):
                            with ui.row().classes("wp-mode-info"):
                                ui.icon(icon, size="1.75rem").classes("shrink-0")
                                with ui.column().classes("wp-mode-text"):
                                    ui.label(i18n.t(name_key)).classes("wp-mode-title")
                                    ui.label(i18n.t(desc_key)).classes("wp-mode-desc")
                            ui.icon("arrow_forward_ios", size="0.875rem").classes("wp-mode-arrow")
                    self.__buttons.append(btn)

        self.__build_confirm_dialog()

    def __build_confirm_dialog(self) -> None:
        self.__dialog = ui.dialog()
        with self.__dialog, ui.card().classes("wp-card wp-dialog-card"):
            with ui.row().classes("items-center gap-2 mb-1"):
                ui.icon("help_outline", size="sm").classes("text-primary")
                ui.label(i18n.t("dialog.title")).classes("text-lg font-bold")
            self.__dialog_msg = ui.label("").classes("wp-dialog-msg")
            self.__dialog_warn = ui.label(i18n.t("dialog.force_warning")).classes("wp-dialog-warn")
            self.__dialog_warn.visible = False
            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button(
                    i18n.t("dialog.cancel"),
                    on_click=self.__cancel_state,
                ).props("no-caps flat color=grey")
                ui.button(
                    i18n.t("dialog.confirm"),
                    on_click=self.__confirm_state,
                ).props("no-caps unelevated color=primary")

    def __request_state(self, state: str) -> None:
        self.__pending_state = state
        state_translated = i18n.t(f"control.{state}")
        if self.__dialog_msg:
            self.__dialog_msg.text = i18n.t("dialog.prompt", state=state_translated)
        if self.__dialog_warn:
            self.__dialog_warn.set_visibility(state == "force")
        if self.__dialog:
            self.__dialog.open()

    def __cancel_state(self) -> None:
        self.__pending_state = ""
        if self.__dialog:
            self.__dialog.close()

    async def __confirm_state(self) -> None:
        target_state = self.__pending_state
        self.__cancel_state()
        if not target_state:
            return

        for btn in self.__buttons:
            btn.disable()

        try:
            try:
                ok = await self.store.service.set_state(target_state)
            except Exception:
                logging.getLogger(__name__).exception("Unable to change the state")
                ui.notify(i18n.t("notify.error"), type="negative", position="top")
                await self.store.refresh()
                return
            if ok:
                state_name = i18n.t(f"control.{target_state}")
                ui.notify(
                    i18n.t("notify.success", state=state_name),
                    type="positive",
                    position="top",
                )
            else:
                ui.notify(
                    i18n.t("notify.failed"),
                    type="warning",
                    position="top",
                )
            await self.store.refresh()
        finally:
            for btn in self.__buttons:
                btn.enable()

    def update(self) -> None:
        snapshot = self.store.snapshot
        if self.__hero:
            self.__hero.update(snapshot.state if snapshot.ok else "-")

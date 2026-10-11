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

from nicegui import events, ui

from ..components import Card, HeatingBars, StateHero, TemperatureGauge, WeatherTile
from ..i18n import i18n
from ..store import SnapshotStore
from .page import Page


class DashboardPage(Page):
    """Main dashboard page displaying real-time system metrics and schedule trigger."""

    path: str = "/"
    title: str = "Wattpilot"

    def __init__(self, store: SnapshotStore) -> None:
        super().__init__(store)
        self.__hero: StateHero | None = None
        self.__temperature: TemperatureGauge | None = None
        self.__loads: HeatingBars | None = None
        self.__weather: WeatherTile | None = None
        self.__switch: ui.switch | None = None
        self.__banner: ui.element | None = None
        self.__updating_switch: bool = False

    def render(self) -> None:
        # Offline banner shown when backend is unreachable
        self.__banner = ui.row().classes("wp-offline-banner")
        self.__banner.visible = False
        with self.__banner:
            ui.icon("warning", size="1.25rem")
            ui.label(i18n.t("status.offline"))

        with ui.element("div").classes("wp-grid"):
            self.__hero = StateHero()
            self.__temperature = TemperatureGauge()
            self.__loads = HeatingBars()
            self.__weather = WeatherTile()

            # Schedule trigger card
            with Card(title_key="trigger.title", icon="alarm"):
                with ui.row().classes("wp-trigger-row"):
                    with ui.column().classes("wp-trigger-text"):
                        ui.label(i18n.t("trigger.label")).classes("wp-trigger-label")
                        ui.label(i18n.t("trigger.hint")).classes("wp-trigger-hint")
                    self.__switch = (
                        ui.switch(
                            on_change=self.__on_trigger,
                        )
                        .props("color=primary")
                        .classes("shrink-0")
                    )

    async def __on_trigger(self, e: events.ValueChangeEventArguments) -> None:
        if self.__updating_switch:
            return
        new_value = bool(e.value)
        try:
            await self.store.service.set_schedule_trigger(new_value)
        except Exception:
            logging.getLogger(__name__).exception("Unable to set the schedule trigger")
            ui.notify(i18n.t("notify.error"), type="negative", position="top")
        # Always refresh so the switch reflects the real backend value.
        await self.store.refresh()
        self.update()

    def update(self) -> None:
        snapshot = self.store.snapshot
        if self.__banner:
            self.__banner.set_visibility(not snapshot.ok)
        if self.__hero:
            self.__hero.update(snapshot.state if snapshot.ok else "-")
        if self.__temperature:
            self.__temperature.update(snapshot.temperature if snapshot.ok else None)
        if self.__loads:
            self.__loads.update(
                snapshot.loads if snapshot.ok else [],
                snapshot.all_loads if snapshot.ok else None,
            )
        if self.__weather:
            self.__weather.update(
                snapshot.cloudiness if snapshot.ok else None,
                snapshot.forecast_time if snapshot.ok else None,
                snapshot.will_run if snapshot.ok else False,
            )
        if self.__switch and self.__switch.value != snapshot.schedule_trigger:
            self.__updating_switch = True
            try:
                self.__switch.value = snapshot.schedule_trigger
            finally:
                self.__updating_switch = False

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

from ..components import Card, SchedulePeriodChart, StateHero
from ..i18n import i18n
from ..service import Snapshot
from ..store import SnapshotStore
from .dashboard import DashboardPage
from .page import Page


class ControlPage(Page):
    """Control page allowing system settings configuration."""

    path: str = "/control"
    title: str = "Control"

    MODES: tuple[tuple[str, str, str, str, str], ...] = DashboardPage.MODES

    def __init__(self, store: SnapshotStore) -> None:
        super().__init__(store)
        self.__hero: StateHero | None = None

        # Settings controls
        self.__temp_schedule_slider: ui.slider | None = None
        self.__temp_schedule_val: ui.label | None = None
        self.__temp_solar_slider: ui.slider | None = None
        self.__temp_solar_val: ui.label | None = None
        self.__temp_force_slider: ui.slider | None = None
        self.__temp_force_val: ui.label | None = None

        self.__start_slider: ui.slider | None = None
        self.__start_val: ui.label | None = None
        self.__stop_slider: ui.slider | None = None
        self.__stop_val: ui.label | None = None
        self.__chart: SchedulePeriodChart | None = None
        self.__save_btn: ui.button | None = None

        self.__settings_initialized: bool = False
        self.__dirty: bool = False
        self.__syncing: bool = False

    def render(self) -> None:
        self.__hero = StateHero()
        self.__build_settings_card()

    def __build_settings_card(self) -> None:
        with Card(title_key="settings.title", icon="tune"):
            ui.label(i18n.t("settings.desc")).classes("wp-subtext")

            # Group 1: Temperatures
            with ui.column().classes("wp-settings-group"):
                with ui.row().classes("wp-settings-header"):
                    ui.icon("thermostat", size="sm")
                    ui.label(i18n.t("settings.temperatures")).classes("wp-settings-title")

                # Schedule temperature
                with ui.column().classes("wp-settings-item"):
                    with ui.row().classes("wp-settings-row"):
                        with ui.column().classes("wp-settings-info"):
                            ui.label(i18n.t("settings.temp_schedule")).classes("wp-settings-label")
                            ui.label(i18n.t("settings.temp_schedule_desc")).classes("wp-settings-desc")
                        self.__temp_schedule_val = ui.label("55.0 °C").classes("wp-settings-value")
                    self.__temp_schedule_slider = ui.slider(
                        min=45.0, max=65.0, step=0.5, value=55.0, on_change=self.__on_temp_change
                    ).props("color=primary")

                # Solar temperature
                with ui.column().classes("wp-settings-item"):
                    with ui.row().classes("wp-settings-row"):
                        with ui.column().classes("wp-settings-info"):
                            ui.label(i18n.t("settings.temp_solar")).classes("wp-settings-label")
                            ui.label(i18n.t("settings.temp_solar_desc")).classes("wp-settings-desc")
                        self.__temp_solar_val = ui.label("60.0 °C").classes("wp-settings-value")
                    self.__temp_solar_slider = ui.slider(
                        min=45.0, max=65.0, step=0.5, value=60.0, on_change=self.__on_temp_change
                    ).props("color=primary")

                # Force temperature
                with ui.column().classes("wp-settings-item"):
                    with ui.row().classes("wp-settings-row"):
                        with ui.column().classes("wp-settings-info"):
                            ui.label(i18n.t("settings.temp_force")).classes("wp-settings-label")
                            ui.label(i18n.t("settings.temp_force_desc")).classes("wp-settings-desc")
                        self.__temp_force_val = ui.label("55.0 °C").classes("wp-settings-value")
                    self.__temp_force_slider = ui.slider(
                        min=45.0, max=65.0, step=0.5, value=55.0, on_change=self.__on_temp_change
                    ).props("color=primary")

            # Group 2: Schedule period
            with ui.column().classes("wp-settings-group"):
                with ui.row().classes("wp-settings-header"):
                    ui.icon("schedule", size="sm")
                    ui.label(i18n.t("settings.period")).classes("wp-settings-title")

                self.__chart = SchedulePeriodChart()

                # Start time
                with ui.column().classes("wp-settings-item"):
                    with ui.row().classes("wp-settings-row"):
                        with ui.column().classes("wp-settings-info"):
                            ui.label(i18n.t("settings.start")).classes("wp-settings-label")
                            ui.label(i18n.t("settings.start_desc")).classes("wp-settings-desc")
                        self.__start_val = ui.label("02:00").classes("wp-settings-value")
                    self.__start_slider = ui.slider(
                        min=0, max=23, step=1, value=2, on_change=self.__on_period_change
                    ).props("color=primary")

                # Stop time
                with ui.column().classes("wp-settings-item"):
                    with ui.row().classes("wp-settings-row"):
                        with ui.column().classes("wp-settings-info"):
                            ui.label(i18n.t("settings.stop")).classes("wp-settings-label")
                            ui.label(i18n.t("settings.stop_desc")).classes("wp-settings-desc")
                        self.__stop_val = ui.label("06:00").classes("wp-settings-value")
                    self.__stop_slider = ui.slider(
                        min=0, max=23, step=1, value=6, on_change=self.__on_period_change
                    ).props("color=primary")

            # Save Button
            with ui.row().classes("wp-settings-actions"):
                self.__save_btn = (
                    ui.button(i18n.t("settings.save"), on_click=self.__save_settings)
                    .props("no-caps unelevated color=primary")
                    .classes("wp-settings-save-btn")
                )

    def __on_temp_change(self) -> None:
        if self.__syncing:
            return
        self.__dirty = True
        if self.__temp_schedule_slider and self.__temp_schedule_val:
            self.__temp_schedule_val.text = f"{self.__temp_schedule_slider.value:.1f} °C"
        if self.__temp_solar_slider and self.__temp_solar_val:
            self.__temp_solar_val.text = f"{self.__temp_solar_slider.value:.1f} °C"
        if self.__temp_force_slider and self.__temp_force_val:
            self.__temp_force_val.text = f"{self.__temp_force_slider.value:.1f} °C"

    def __on_period_change(self) -> None:
        if self.__syncing:
            return
        self.__dirty = True
        start = int(self.__start_slider.value) if self.__start_slider else 0
        stop = int(self.__stop_slider.value) if self.__stop_slider else 0
        if self.__start_val:
            self.__start_val.text = f"{start:02d}:00"
        if self.__stop_val:
            self.__stop_val.text = f"{stop:02d}:00"
        if self.__chart:
            self.__chart.update(start, stop)
        if self.__save_btn:
            if start == stop:
                self.__save_btn.disable()
            else:
                self.__save_btn.enable()

    async def __save_settings(self) -> None:
        if not self.__save_btn:
            return

        start = int(self.__start_slider.value) if self.__start_slider else 0
        stop = int(self.__stop_slider.value) if self.__stop_slider else 0
        if start == stop:
            ui.notify(i18n.t("settings.equal_hours_error"), type="warning", position="top")
            return

        t_sched = float(self.__temp_schedule_slider.value) if self.__temp_schedule_slider else 55.0
        t_solar = float(self.__temp_solar_slider.value) if self.__temp_solar_slider else 60.0
        t_force = float(self.__temp_force_slider.value) if self.__temp_force_slider else 55.0

        self.__save_btn.disable()
        try:
            try:
                ok = await self.store.service.set_settings(
                    temperature_schedule=t_sched,
                    temperature_solar=t_solar,
                    temperature_force=t_force,
                    schedule_start=start,
                    schedule_stop=stop,
                )
            except Exception:
                logging.getLogger(__name__).exception("Unable to save settings")
                ui.notify(i18n.t("notify.settings_failed"), type="negative", position="top")
                await self.store.refresh()
                return

            if ok:
                ui.notify(i18n.t("notify.settings_saved"), type="positive", position="top")
                self.__dirty = False
            else:
                ui.notify(i18n.t("notify.settings_failed"), type="warning", position="top")
            await self.store.refresh()
        finally:
            if start != stop:
                self.__save_btn.enable()

    def __sync_settings_from_snapshot(self, snapshot: Snapshot) -> None:
        self.__syncing = True
        try:
            if snapshot.temperature_schedule is not None and self.__temp_schedule_slider:
                self.__temp_schedule_slider.value = snapshot.temperature_schedule
                if self.__temp_schedule_val:
                    self.__temp_schedule_val.text = f"{snapshot.temperature_schedule:.1f} °C"

            if snapshot.temperature_solar is not None and self.__temp_solar_slider:
                self.__temp_solar_slider.value = snapshot.temperature_solar
                if self.__temp_solar_val:
                    self.__temp_solar_val.text = f"{snapshot.temperature_solar:.1f} °C"

            if snapshot.temperature_force is not None and self.__temp_force_slider:
                self.__temp_force_slider.value = snapshot.temperature_force
                if self.__temp_force_val:
                    self.__temp_force_val.text = f"{snapshot.temperature_force:.1f} °C"

            if snapshot.schedule_start is not None and self.__start_slider:
                self.__start_slider.value = snapshot.schedule_start
                if self.__start_val:
                    self.__start_val.text = f"{snapshot.schedule_start:02d}:00"

            if snapshot.schedule_stop is not None and self.__stop_slider:
                self.__stop_slider.value = snapshot.schedule_stop
                if self.__stop_val:
                    self.__stop_val.text = f"{snapshot.schedule_stop:02d}:00"

            if self.__chart and snapshot.schedule_start is not None and snapshot.schedule_stop is not None:
                self.__chart.update(snapshot.schedule_start, snapshot.schedule_stop)

            if self.__save_btn and snapshot.schedule_start is not None and snapshot.schedule_stop is not None:
                if snapshot.schedule_start == snapshot.schedule_stop:
                    self.__save_btn.disable()
                else:
                    self.__save_btn.enable()
        finally:
            self.__syncing = False
            self.__dirty = False

    def update(self) -> None:
        snapshot = self.store.snapshot
        if self.__hero:
            self.__hero.update(snapshot.state if snapshot.ok else "-")

        if snapshot.ok and snapshot.temperature_schedule is not None:
            if not self.__settings_initialized:
                self.__sync_settings_from_snapshot(snapshot)
                self.__settings_initialized = True
            elif not self.__dirty:
                self.__sync_settings_from_snapshot(snapshot)

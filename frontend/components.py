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

from datetime import datetime
from typing import ClassVar

from nicegui import ui

from wattpilot.settings import get_schedule_duration

from .i18n import i18n


class Card:
    """Base glass card container with optional icon and title label."""

    def __init__(
        self,
        title_key: str | None = None,
        icon: str | None = None,
        classes: str = "",
    ) -> None:
        self.__title_key = title_key
        self.__icon = icon
        card_classes = f"wp-card {classes}".strip() if classes else "wp-card"
        self.__card = ui.card().classes(card_classes)

    def __enter__(self) -> Card:
        self.__card.__enter__()
        if self.__title_key or self.__icon:
            with ui.row().classes("wp-card-header"):
                if self.__title_key:
                    ui.label(i18n.t(self.__title_key)).classes("wp-label")
                if self.__icon:
                    ui.icon(self.__icon).classes("wp-card-header-icon")
        return self

    def __exit__(self, *exc: object) -> None:
        self.__card.__exit__(*exc)


class StateHero:
    """Large hero tile displaying current system state with icon, description, and glow."""

    STATE_CONFIG: ClassVar[dict[str, tuple[str, str, str]]] = {
        "halt": ("state.halt", "power_settings_new", "state.desc.halt"),
        "idle": ("state.idle", "hourglass_empty", "state.desc.idle"),
        "force": ("state.force", "bolt", "state.desc.force"),
        "schedule": ("state.schedule", "schedule", "state.desc.schedule"),
        "solar": ("state.solar", "wb_sunny", "state.desc.solar"),
    }

    def __init__(self) -> None:
        self.__active_state_class: str = ""
        self.__card = ui.card().classes("wp-card wp-hero wp-hero-span")
        with self.__card:
            with ui.row().classes("wp-hero-row"):
                with ui.column().classes("wp-hero-text"):
                    ui.label(i18n.t("state.title")).classes("wp-label")
                    self.__name_label = ui.label("-").classes("wp-value text-3xl font-light")
                    self.__desc_label = ui.label(i18n.t("state.connecting")).classes("wp-subtext")
                self.__icon_circle = ui.element("div").classes("wp-icon-circle shrink-0")
                with self.__icon_circle:
                    self.__icon = ui.icon("sync", size="2rem")

    def update(self, state: str) -> None:
        if self.__active_state_class:
            self.__card.classes(remove=self.__active_state_class)

        info = self.STATE_CONFIG.get(state)
        if info:
            name_key, icon_name, desc_key = info
            self.__name_label.text = i18n.t(name_key)
            self.__desc_label.text = i18n.t(desc_key)
            self.__icon.name = icon_name
            self.__active_state_class = f"wp-hero--{state}"
        else:
            self.__name_label.text = state.title() if state and state != "-" else "-"
            self.__desc_label.text = i18n.t("state.unknown")
            self.__icon.name = "help_outline"
            self.__active_state_class = "wp-hero--unknown"

        self.__card.classes(add=self.__active_state_class)


class TemperatureGauge:
    """Circular temperature gauge showing boiler temperature in °C."""

    def __init__(self) -> None:
        self.__card = ui.card().classes("wp-card wp-gauge-card")
        with self.__card:
            ui.label(i18n.t("temp.title")).classes("wp-label self-start")
            with ui.row().classes("wp-gauge-row"):
                self.__progress = ui.circular_progress(
                    value=0.0,
                    min=0.0,
                    max=100.0,
                    size="9.5rem",
                    show_value=False,
                ).props("track-color=grey-3 thickness=0.15")
                with self.__progress:
                    with ui.column().classes("wp-gauge-center"):
                        self.__temp_label = ui.label("-").classes("wp-value text-3xl font-light")
                        ui.label(i18n.t("temp.unit")).classes("wp-gauge-unit")

    def update(self, temp: float | None) -> None:
        if temp is None or temp < 0:
            self.__temp_label.text = "-"
            self.__progress.value = 0.0
            self.__progress.props("color=grey")
            return

        self.__temp_label.text = f"{temp:.1f}"
        self.__progress.value = max(0.0, min(100.0, temp))
        if temp < 45.0:
            self.__progress.props("color=blue")
        elif temp < 60.0:
            self.__progress.props("color=orange")
        else:
            self.__progress.props("color=red")


class HeatingBars:
    """Displays heating elements as progressive increasing bars that fill up when active."""

    def __init__(self) -> None:
        self.__card = ui.card().classes("wp-card wp-bars-card")
        with self.__card:
            with ui.row().classes("w-full items-center justify-between no-wrap gap-2"):
                ui.label(i18n.t("loads.title")).classes("wp-label")
                self.__count_badge = ui.badge("0/3", color="primary").props("rounded").classes("shrink-0")
            self.__bars_container = ui.element("div").classes("wp-bars-container")

        self.__current_all_ids: list[str] = []
        self.__current_active_ids: list[str] = []
        self.__bar_nodes: dict[str, tuple[ui.element, ui.element]] = {}

    def update(self, active_ids: list[str], all_ids: list[str] | None = None) -> None:
        target_all = sorted(all_ids) if all_ids else (self.__current_all_ids or sorted(active_ids))
        sorted_active = sorted(active_ids)

        if target_all != self.__current_all_ids:
            self.__current_all_ids = target_all
            self.__build_bars(target_all)

        self.__count_badge.text = i18n.t(
            "loads.active_of_total",
            active=len(sorted_active),
            total=len(target_all),
        )
        self.__count_badge.props(f"color={'primary' if sorted_active else 'grey'}")

        active_set = set(sorted_active)
        for element_id, (col, track) in self.__bar_nodes.items():
            if element_id in active_set:
                col.classes(add="is-active")
                track.classes(add="is-active")
            else:
                col.classes(remove="is-active")
                track.classes(remove="is-active")

        self.__current_active_ids = sorted_active

    def __build_bars(self, all_ids: list[str]) -> None:
        self.__bars_container.clear()
        self.__bar_nodes.clear()
        with self.__bars_container:
            for index, element_id in enumerate(all_ids):
                stage = index + 1
                col = ui.element("div").classes(f"wp-bar-column wp-bar-col-{stage}")
                with col:
                    track = ui.element("div").classes(f"wp-bar-track wp-bar-track-{stage}")
                    with track:
                        ui.element("div").classes(f"wp-bar-fill wp-bar-fill-{stage}")
                    ui.label(element_id).classes(f"wp-bar-label wp-bar-label-{stage}")
                    col.tooltip(i18n.t("loads.element", id=element_id))
                self.__bar_nodes[element_id] = (col, track)


# Backwards compatibility alias
LoadChips = HeatingBars


class WeatherTile:
    """Weather forecast and solar schedule trigger prediction."""

    def __init__(self) -> None:
        self.__card = ui.card().classes("wp-card")
        with self.__card:
            with ui.row().classes("wp-card-header"):
                ui.label(i18n.t("weather.title")).classes("wp-label")
                self.__time_label = ui.label("-").classes("wp-subtext text-xs")
            with ui.row().classes("wp-weather-summary"):
                with ui.row().classes("wp-weather-info"):
                    self.__icon = ui.icon("cloud", size="2.5rem").classes("wp-cloud-icon")
                    with ui.column().classes("gap-0"):
                        self.__cloud_label = ui.label("-").classes("wp-value text-2xl")
                        ui.label(i18n.t("weather.cloudiness")).classes("wp-subtext text-xs")
            self.__progress = (
                ui.linear_progress(value=0.0, show_value=False).props("rounded size=8px").classes("wp-cloud-progress")
            )
            self.__trigger_label = ui.label(i18n.t("weather.pending")).classes("wp-weather-forecast-badge")

    def update(self, cloudiness: int | None, forecast_time: datetime | None, will_run: bool) -> None:
        if cloudiness is None or cloudiness < 0:
            self.__cloud_label.text = "-"
            self.__progress.value = 0.0
            self.__trigger_label.text = i18n.t("weather.unavailable")
            self.__icon.name = "cloud_off"
            self.__time_label.text = "-"
            return

        self.__cloud_label.text = f"{cloudiness}%"
        self.__progress.value = cloudiness / 100.0

        if cloudiness < 20:
            self.__icon.name = "cloud_queue"
        else:
            self.__icon.name = "cloud"

        if forecast_time:
            local_time = forecast_time.astimezone()
            self.__time_label.text = i18n.t("weather.forecast_at", time=local_time.strftime("%H:%M"))
        else:
            self.__time_label.text = "-"

        if will_run:
            self.__trigger_label.text = i18n.t("weather.will_run")
            self.__trigger_label.classes(remove="is-solar", add="is-run")
        else:
            self.__trigger_label.text = i18n.t("weather.will_not_run")
            self.__trigger_label.classes(remove="is-run", add="is-solar")


class SchedulePeriodChart:
    """Visual 24-hour timeline displaying off-peak scheduled heating window."""

    def __init__(self) -> None:
        self.__container = ui.column().classes("wp-settings-item")
        with self.__container:
            with ui.row().classes("wp-period-header"):
                self.__duration_label = ui.label("").classes("wp-period-duration")
                self.__now_label = ui.label("").classes("wp-period-now")
            self.__html = ui.html("", tag="div").classes("w-full")

    def update(self, start: int, stop: int, now_time: datetime | None = None) -> None:
        local_now = now_time or datetime.now().astimezone()
        duration = get_schedule_duration(start, stop)
        if start == stop:
            self.__duration_label.text = i18n.t("settings.equal_hours_error")
            self.__duration_label.classes(add="is-invalid")
        else:
            self.__duration_label.text = i18n.t(
                "settings.duration",
                start=f"{start:02d}",
                stop=f"{stop:02d}",
                duration=duration,
            )
            self.__duration_label.classes(remove="is-invalid")

        self.__now_label.text = i18n.t("settings.now_indicator", time=local_now.strftime("%H:%M"))
        self.__html.content = self.__generate_period_svg(start, stop, local_now)

    @staticmethod
    def __generate_period_svg(start: int, stop: int, now_time: datetime | None = None) -> str:
        """Generate SVG visualization of 24h schedule period with midnight wrap-around."""
        track_x = 10
        track_y = 14
        track_w = 460
        track_h = 20
        slot_w = track_w / 24.0

        rects: list[str] = []
        if start != stop:
            if start < stop:
                rx = track_x + start * slot_w
                rw = (stop - start) * slot_w
                rects.append(
                    f'<rect x="{rx:.1f}" y="{track_y}" width="{rw:.1f}" height="{track_h}" rx="6" '
                    f'class="wp-period-active" />'
                )
            else:
                # Wraps across midnight: two segments [start..24) and [0..stop)
                rx1 = track_x + start * slot_w
                rw1 = (24 - start) * slot_w
                rx2 = track_x
                rw2 = stop * slot_w
                rects.append(
                    f'<rect x="{rx1:.1f}" y="{track_y}" width="{rw1:.1f}" height="{track_h}" rx="6" '
                    f'class="wp-period-active" />'
                )
                rects.append(
                    f'<rect x="{rx2:.1f}" y="{track_y}" width="{rw2:.1f}" height="{track_h}" rx="6" '
                    f'class="wp-period-active" />'
                )

        # Major hour labels & ticks: 0, 6, 12, 18, 24
        ticks: list[str] = []
        labels: list[str] = []
        for h in (0, 6, 12, 18, 24):
            lx = track_x + h * slot_w
            ticks.append(
                f'<line x1="{lx:.1f}" y1="{track_y + track_h}" x2="{lx:.1f}" y2="{track_y + track_h + 4}" '
                f'class="wp-period-tick" />'
            )
            anchor = "start" if h == 0 else ("end" if h == 24 else "middle")
            labels.append(
                f'<text x="{lx:.1f}" y="{track_y + track_h + 16}" text-anchor="{anchor}" '
                f'class="wp-period-tick-label">{h:02d}:00</text>'
            )

        # Hour dividers (subtle)
        dividers: list[str] = []
        for h in range(1, 24):
            dx = track_x + h * slot_w
            dividers.append(
                f'<line x1="{dx:.1f}" y1="{track_y}" x2="{dx:.1f}" y2="{track_y + track_h}" '
                f'class="wp-period-divider" />'
            )

        # Current time marker
        marker = ""
        if now_time:
            local_hour = now_time.hour + now_time.minute / 60.0
            mx = track_x + local_hour * slot_w
            marker = (
                f'<line x1="{mx:.1f}" y1="5" x2="{mx:.1f}" y2="{track_y + track_h + 4}" '
                f'class="wp-period-marker" />'
                f'<polygon points="{mx:.1f},11 {mx - 4:.1f},4 {mx + 4:.1f},4" class="wp-period-marker-needle" />'
            )

        return (
            f'<svg viewBox="0 0 480 56" width="100%" height="auto" class="wp-period-svg" '
            f'xmlns="http://www.w3.org/2000/svg">'
            f'<rect x="{track_x}" y="{track_y}" width="{track_w}" height="{track_h}" rx="6" '
            f'class="wp-period-track" />'
            + "".join(rects)
            + "".join(dividers)
            + "".join(ticks)
            + "".join(labels)
            + marker
            + "</svg>"
        )

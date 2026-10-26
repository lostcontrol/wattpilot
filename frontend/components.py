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

from datetime import UTC, datetime
from typing import Any, ClassVar

from nicegui import ui

from wattpilot.database import MetricPoint
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
    """Solar production forecast and off-peak schedule trigger prediction."""

    def __init__(self) -> None:
        self.__card = ui.card().classes("wp-card")
        with self.__card:
            with ui.row().classes("wp-card-header"):
                ui.label(i18n.t("weather.title")).classes("wp-label")
                self.__date_label = ui.label("-").classes("wp-subtext text-xs")
            with ui.row().classes("wp-weather-summary"):
                with ui.row().classes("wp-weather-info"):
                    self.__icon = ui.icon("wb_sunny", size="2.5rem").classes("wp-solar-forecast-icon")
                    with ui.column().classes("gap-0"):
                        self.__forecast_label = ui.label("-").classes("wp-value text-2xl")
                        ui.label(i18n.t("weather.production")).classes("wp-subtext text-xs")
            self.__progress = (
                ui.linear_progress(value=0.0, show_value=False).props("rounded size=8px").classes("wp-solar-progress")
            )
            self.__trigger_label = ui.label(i18n.t("weather.pending")).classes("wp-weather-forecast-badge")

    def update(
        self,
        solar_forecast: float | None,
        forecast_date: str | None,
        will_run: bool,
        threshold: float | None = None,
    ) -> None:
        if solar_forecast is None or solar_forecast < 0:
            self.__forecast_label.text = "-"
            self.__progress.value = 0.0
            self.__trigger_label.text = i18n.t("weather.unavailable")
            self.__icon.name = "wb_twilight"
            self.__date_label.text = "-"
            return

        self.__forecast_label.text = f"{solar_forecast:.1f} kWh"
        max_val = max((threshold or 15.0) * 2.0, 30.0)
        self.__progress.value = min(1.0, max(0.0, solar_forecast / max_val))

        if forecast_date:
            self.__date_label.text = i18n.t("weather.forecast_for", date=forecast_date)
        else:
            self.__date_label.text = "-"

        if will_run:
            self.__icon.name = "wb_twilight"
            self.__trigger_label.text = i18n.t("weather.will_run")
            self.__trigger_label.classes(remove="is-solar", add="is-run")
        else:
            self.__icon.name = "wb_sunny"
            self.__trigger_label.text = i18n.t("weather.will_not_run")
            self.__trigger_label.classes(remove="is-run", add="is-solar")


# Backwards compatibility alias
SolarForecastTile = WeatherTile


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


class HistoryChart:
    """Card spanning 2 columns showing boiler temperature & loads chart with zoom controls."""

    RANGE_OPTIONS: ClassVar[tuple[tuple[int, str], ...]] = (
        (1, "chart.range_1d"),
        (3, "chart.range_3d"),
        (7, "chart.range_7d"),
    )

    def __init__(self) -> None:
        self.__selected_days: int = 1
        self.__last_history_len: int = -1
        self.__last_history_ts: int = -1
        self.__cached_history: list[MetricPoint] = []
        self.__cached_total_loads: int = 3
        self.__range_buttons: dict[int, ui.button] = {}

        self.__card = ui.card().classes("wp-card wp-col-span-2")
        with self.__card:
            with ui.row().classes("wp-chart-header"):
                ui.label(i18n.t("chart.title")).classes("wp-label")
                with ui.row().classes("wp-chart-ranges"):
                    for days, label_key in self.RANGE_OPTIONS:
                        btn = (
                            ui.button(
                                i18n.t(label_key),
                                on_click=lambda d=days: self.__set_range(d),
                            )
                            .props("dense flat no-caps size=sm")
                            .classes("wp-chart-range-btn")
                        )
                        if days == self.__selected_days:
                            btn.classes(add="is-active")
                        self.__range_buttons[days] = btn

            self.__empty_label = ui.label(i18n.t("chart.empty")).classes("wp-chart-empty text-center py-8 w-full")
            self.__chart = ui.echart(self.__build_options([], 3, 1)).classes("wp-echart w-full")
            self.__chart.visible = False

    def __set_range(self, days: int) -> None:
        if self.__selected_days == days:
            return
        self.__selected_days = days
        for d, btn in self.__range_buttons.items():
            if d == days:
                btn.classes(add="is-active")
            else:
                btn.classes(remove="is-active")
        self.__update_chart_options(
            self.__build_options(self.__cached_history, self.__cached_total_loads, self.__selected_days)
        )

    def __update_chart_options(self, options: dict[str, Any]) -> None:
        self.__chart.options.clear()
        self.__chart.options.update(options)
        self.__chart.update()

    def update(
        self,
        history: list[MetricPoint],
        total_loads: int = 3,
    ) -> None:
        new_len = len(history)
        new_ts = history[-1].timestamp if history else -1

        if new_len != self.__last_history_len or new_ts != self.__last_history_ts:
            self.__last_history_len = new_len
            self.__last_history_ts = new_ts
            self.__cached_history = history
            self.__cached_total_loads = max(1, total_loads)

            if not history:
                self.__empty_label.set_visibility(True)
                self.__chart.set_visibility(False)
            else:
                self.__empty_label.set_visibility(False)
                self.__chart.set_visibility(True)
                self.__update_chart_options(
                    self.__build_options(history, self.__cached_total_loads, self.__selected_days)
                )

    @staticmethod
    def __build_options(
        history: list[MetricPoint],
        total_loads: int,
        range_days: int,
    ) -> dict[str, Any]:
        temp_data: list[list[float | int]] = []
        load_data: list[list[int]] = []
        prev_p: MetricPoint | None = None
        for p in history:
            ts_ms = p.timestamp * 1000
            if prev_p is not None and (p.timestamp - prev_p.timestamp) > 120 and prev_p.loads > 0:
                load_data.append([(prev_p.timestamp + 60) * 1000, 0])
            temp_data.append([ts_ms, p.temperature])
            load_data.append([ts_ms, p.loads])
            prev_p = p

        now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
        start_ms = now_ms - (range_days * 86400 * 1000)

        if history:
            time_since_last_ms = now_ms - history[-1].timestamp * 1000
            if time_since_last_ms <= 120_000:
                load_data.append([now_ms, history[-1].loads])
                temp_data.append([now_ms, history[-1].temperature])
            elif history[-1].loads > 0:
                load_data.append([(history[-1].timestamp + 60) * 1000, 0])

        temp_name = i18n.t("chart.temperature")
        loads_name = i18n.t("chart.loads")

        return {
            "animation": False,
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "cross"},
            },
            "legend": {
                "data": [
                    temp_name,
                    {"name": loads_name, "icon": "roundRect"},
                ],
                "top": 0,
                "textStyle": {"color": "#64748b"},
            },
            "grid": {
                "left": 40,
                "right": 40,
                "top": 35,
                "bottom": 25,
            },
            "xAxis": {
                "type": "time",
                "axisLine": {"lineStyle": {"color": "#94a3b8"}},
                "axisLabel": {"color": "#64748b", "hideOverlap": True},
                "splitLine": {"show": False},
            },
            "yAxis": [
                {
                    "type": "value",
                    "name": "°C",
                    "position": "left",
                    "scale": True,
                    "splitLine": {"lineStyle": {"color": "rgba(148, 163, 184, 0.15)"}},
                    "axisLabel": {"color": "#f97316"},
                },
                {
                    "type": "value",
                    "name": "",
                    "position": "right",
                    "min": 0,
                    "max": max(1, total_loads),
                    "minInterval": 1,
                    "splitLine": {"show": False},
                    "axisLabel": {"color": "#3b82f6"},
                },
            ],
            "dataZoom": [
                {
                    "type": "inside",
                    "xAxisIndex": 0,
                    "filterMode": "none",
                    "startValue": start_ms,
                    "endValue": now_ms,
                }
            ],
            "series": [
                {
                    "name": loads_name,
                    "type": "line",
                    "step": "end",
                    "yAxisIndex": 1,
                    "data": load_data,
                    "showSymbol": False,
                    "itemStyle": {
                        "color": "#3b82f6",
                    },
                    "lineStyle": {
                        "color": "rgba(59, 130, 246, 0.7)",
                        "width": 1.5,
                    },
                    "areaStyle": {
                        "color": "rgba(59, 130, 246, 0.35)",
                    },
                    "z": 1,
                },
                {
                    "name": temp_name,
                    "type": "line",
                    "yAxisIndex": 0,
                    "data": temp_data,
                    "smooth": True,
                    "showSymbol": False,
                    "lineStyle": {"color": "#f97316", "width": 2},
                    "areaStyle": {
                        "color": {
                            "type": "linear",
                            "x": 0,
                            "y": 0,
                            "x2": 0,
                            "y2": 1,
                            "colorStops": [
                                {"offset": 0, "color": "rgba(249, 115, 22, 0.2)"},
                                {"offset": 1, "color": "rgba(249, 115, 22, 0.0)"},
                            ],
                        }
                    },
                    "z": 3,
                },
            ],
        }

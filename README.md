# Wattpilot

[![CI](https://github.com/lostcontrol/wattpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/lostcontrol/wattpilot/actions/workflows/ci.yml)

## Introduction

We have recently installed solar panels (photovoltaic). One of the challenge is to increase your auto-consumption. One of the main consumer we have is the water boiler. It used to run at night to benefit from off-peak tariff. We decided to build a system to pilot the water boiler in a way that it would improve the auto-consumption.

The system runs Axitec solar panels with a [Fronius Symo](https://www.fronius.com/en/photovoltaics/products/all-products/inverters/fronius-symo/fronius-symo-10-0-3-m) inverter. Fronius offers the [Ohmpilot](https://www.fronius.com/en/photovoltaics/products/all-products/solutions/fronius-solution-for-heat-generation/fronius-ohmpilot/fronius-ohmpilot) in order to do this. However, it does not take into account weather forecast and the cost is rather high. We wanted to make something DIY and more flexible.

In order to keep the cost low, we didn't want to continuously adjust the output power like the Ohmpilot does. Instead, we are going to control separately the 3 resistances that are in the boiler.

## Features

* Wattpilot can control from 1 to N loads, switching them on and off based on the exported power.
* A schedule can be define which is meant to warm the water during the off-peak period.
* Just before the scheduled period, the weather forecast for the coming day will be fetched from [OpenWeather](https://openweathermap.org/) and if the sky is going to be very cloudy, the water will be warmed during the scheduled period.
* The next scheduled period can be set manually to be triggered in any case.
* A force mode allows the user to start/stop the heating manually at any time.

## Running

Install dependencies:

```bash
uv sync
```

Run in development mode with fake hardware devices:

```bash
uv run python wattpilot.py --fake-devices
```

Open <http://localhost:8080> in your browser (or <http://localhost/> via `docker compose up`, and <http://localhost:8088/> via `docker compose -f docker-compose.development.yml up`).

The web interface is built with [NiceGUI](https://nicegui.io/) located in the `frontend/` directory. It is optimized for mobile and desktop, and supports multiple languages (English and French by default, configured via JSON files in `frontend/locales/`).

Page-level authentication can be added by providing a custom `AuthPolicy` subclass to `FrontendApp`. It only gates the pages, not the static files or the websocket.

## Configuration & UI Settings

Configuration is loaded in cascading order (later files override earlier ones):
1. `config.ini`: Base configuration defaults.
2. `config.ini.local`: Local hardware/site configuration.
3. `config.ini.settings` (or custom path via `WATTPILOT_SETTINGS` environment variable): UI-configured settings with highest priority.

From the web UI (under **Control**), you can configure:
* **Boiler temperatures** for scheduled, solar surplus, and forced heating modes (45.0 to 65.0 °C in 0.5 °C increments).
* **Schedule off-peak window** (start and end hour in local system timezone, with support for midnight wrap-around such as 23:00 to 02:00).
* An interactive 24-hour visual timeline of the off-peak period.

Changes take effect immediately and are saved to the persistent settings file. In Docker, persist this file by mounting a volume (e.g. `/data` with `WATTPILOT_SETTINGS=/data/config.ini.settings`).

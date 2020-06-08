# Wattpilot

## Introduction

We have recently installed solar panels (photovoltaic). One of the challenge is to increase your auto-consumption. One of the main consumer we have is the water boiler. It used to run at night to benefit from off-peak tariff. We decided to build a system to pilot the water boiler in a way that it would improve the auto-consumption.

The system runs Axitec solar panels with a [Fronius Symo](https://www.fronius.com/en/photovoltaics/products/all-products/inverters/fronius-symo/fronius-symo-10-0-3-m) inverter. Fronius offers the [Ohmpilot](https://www.fronius.com/en/photovoltaics/products/all-products/solutions/fronius-solution-for-heat-generation/fronius-ohmpilot/fronius-ohmpilot) in order to do this. However, it does not take into account weather forecast and the cost is rather high. We wanted to make something DIY and smarter/more flexible.

In order to keep the cost low, we didn't want to continuously adjust the output power like the Ohmpilot does. Instead, we are going to control separately the 3 resistances that are in the boiler.

## Features

* Wattpilot can control from 1 to N loads, switching them on and off based on the exported power.
* A schedule can be define which is meant to warm the water during the off-peak period.
* Just before the scheduled period, the weather forecast for the coming day will be fetched from [OpenWeather](https://openweathermap.org/) and if the sky is going to be very cloudy, the water will be warmed during the scheduled period.
* The next scheduled period can be set manually to be triggered in any case.
* A force mode allows the user to start/stop the heating manually at any time.
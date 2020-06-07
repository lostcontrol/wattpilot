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

class WattPilotApp:

    wattpilot = None

    @staticmethod
    def get_current_state():
        return {"state": WattPilotApp.wattpilot.state.get()}

    @staticmethod
    def set_current_state(state):
        result = False
        if state["state"] == "halt":
            result = WattPilotApp.wattpilot.halt().get()
        elif state["state"] == "idle":
            result = WattPilotApp.wattpilot.idle().get()
        elif state["state"] == "force":
            result = WattPilotApp.wattpilot.force().get()
        else:
            return "Invalid state", 405
        return {} if result else ("Unable to change state", 406)

    @staticmethod
    def get_schedule_trigger():
        return WattPilotApp.wattpilot.get_schedule_trigger().get()

    @staticmethod
    def set_schedule_trigger(trigger):
        return WattPilotApp.wattpilot.set_schedule_trigger(trigger).get()

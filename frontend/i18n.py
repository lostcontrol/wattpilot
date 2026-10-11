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

import json
from pathlib import Path

from nicegui import ui


class I18n:
    """Internationalization manager with nested JSON loader and auto browser language detection."""

    def __init__(self, locales_dir: Path | None = None, default_lang: str = "en") -> None:
        self.__locales_dir = locales_dir or (Path(__file__).parent / "locales")
        self.__default_lang = default_lang
        self.__current_lang = default_lang
        self.__translations: dict[str, dict[str, str]] = {}
        self.__load_all_locales()

    @property
    def current_lang(self) -> str:
        try:
            req = getattr(ui.context.client, "request", None)
            if req:
                cookie_lang = req.cookies.get("lang")
                if cookie_lang in self.__translations:
                    return cookie_lang
                if req.headers.get("accept-language", "").split(",")[0].strip().lower().startswith("fr"):
                    return "fr"
        except Exception:
            pass
        return self.__current_lang

    @property
    def supported_langs(self) -> list[str]:
        return sorted(self.__translations.keys())

    def set_lang(self, lang: str) -> None:
        if lang in self.__translations:
            self.__current_lang = lang

    def t(self, key: str, **kwargs: object) -> str:
        active_lang = self.current_lang
        lang_dict = self.__translations.get(
            active_lang,
            self.__translations.get(self.__default_lang, {}),
        )
        template = lang_dict.get(key)
        if template is None:
            default_dict = self.__translations.get(self.__default_lang, {})
            template = default_dict.get(key, key)
        if kwargs:
            try:
                return template.format(**kwargs)
            except KeyError, ValueError:
                return template
        return template

    def __flatten_dict(self, data: dict[str, object], prefix: str = "") -> dict[str, str]:
        flat: dict[str, str] = {}
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                flat.update(self.__flatten_dict(value, prefix=full_key))
            elif isinstance(value, str):
                flat[full_key] = value
        return flat

    def __load_all_locales(self) -> None:
        if not self.__locales_dir.is_dir():
            return
        for file in self.__locales_dir.glob("*.json"):
            try:
                content = file.read_text(encoding="utf-8")
                raw_data = json.loads(content)
                if isinstance(raw_data, dict):
                    self.__translations[file.stem] = self.__flatten_dict(raw_data)
            except OSError, json.JSONDecodeError:
                continue


# Global default instance
i18n = I18n()

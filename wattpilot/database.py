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
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .actor import WattPilotActor

logger = logging.getLogger(__name__)

DEFAULT_DB_FILE: Final[str] = "wattpilot.db"
RETENTION_SECONDS: Final[int] = 7 * 24 * 3600


@dataclass(frozen=True)
class MetricPoint:
    timestamp: int
    temperature: float
    loads: int


class Base(DeclarativeBase):
    pass


class MetricRecord(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[int] = mapped_column(index=True, nullable=False)
    temperature: Mapped[float] = mapped_column(nullable=False)
    loads: Mapped[int] = mapped_column(nullable=False)


class Database(WattPilotActor):
    def __init__(self, path: str | Path | None = None) -> None:
        super().__init__()
        raw_path = path or os.environ.get("WATTPILOT_DB", DEFAULT_DB_FILE)
        self.__path: Path = Path(raw_path).expanduser().resolve()
        self.__path.parent.mkdir(parents=True, exist_ok=True)
        self.__engine: Engine = create_engine(f"sqlite:///{self.__path}")
        Base.metadata.create_all(self.__engine)
        logger.info("Initialized metrics database at %s", self.__path)

    def record(self, temperature: float | int, loads: int, timestamp: int | None = None) -> None:
        now_ts = int(datetime.now(tz=UTC).timestamp()) if timestamp is None else int(timestamp)
        cutoff = now_ts - RETENTION_SECONDS
        with Session(self.__engine) as session:
            session.execute(delete(MetricRecord).where(MetricRecord.timestamp < cutoff))
            session.add(
                MetricRecord(
                    timestamp=now_ts,
                    temperature=round(float(temperature), 2),
                    loads=int(loads),
                )
            )
            session.commit()

    def get_history(self, since_timestamp: int | None = None) -> list[MetricPoint]:
        cutoff = (
            int(datetime.now(tz=UTC).timestamp()) - RETENTION_SECONDS
            if since_timestamp is None
            else int(since_timestamp)
        )
        stmt = (
            select(MetricRecord)
            .where(MetricRecord.timestamp >= cutoff)
            .order_by(MetricRecord.timestamp.asc(), MetricRecord.id.asc())
        )
        with Session(self.__engine) as session:
            rows = session.scalars(stmt).all()
            return [
                MetricPoint(
                    timestamp=row.timestamp,
                    temperature=row.temperature,
                    loads=row.loads,
                )
                for row in rows
            ]

    def on_stop(self) -> None:
        super().on_stop()
        self.__engine.dispose()

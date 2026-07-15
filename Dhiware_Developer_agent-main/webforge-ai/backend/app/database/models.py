from __future__ import annotations
from datetime import datetime
from typing import Optional
import json

from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    framework: Mapped[str] = mapped_column(String(50), default="unknown")
    status: Mapped[str] = mapped_column(String(50), default="idle")
    root_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preview_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    messages: Mapped[list[MessageModel]] = relationship(back_populates="project", cascade="all, delete-orphan")
    snapshots: Mapped[list[SnapshotModel]] = relationship(back_populates="project", cascade="all, delete-orphan")

    @property
    def metadata_dict(self) -> dict:
        if not self.metadata_json:
            return {}
        return json.loads(self.metadata_json)

    def set_metadata(self, data: dict) -> None:
        self.metadata_json = json.dumps(data)


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text, default="")
    agent_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_refs_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    project: Mapped[ProjectModel] = relationship(back_populates="messages")


class SnapshotModel(Base):
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    message: Mapped[str] = mapped_column(Text)
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    project: Mapped[ProjectModel] = relationship(back_populates="snapshots")

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from auth_service.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Role(Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_transitory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    transitions_to: Mapped[str | None] = mapped_column(String(80), ForeignKey("roles.name"), nullable=True)
    requires_role: Mapped[str | None] = mapped_column(String(80), ForeignKey("roles.name"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    incompatible_roles: Mapped[list[RoleIncompatibility]] = relationship(
        back_populates="role",
        foreign_keys="RoleIncompatibility.role_name",
        cascade="all, delete-orphan",
    )


class RoleIncompatibility(Base):
    __tablename__ = "role_incompatibilities"
    __table_args__ = (
        UniqueConstraint(
            "role_name", "incompatible_with", name="uq_role_incompatibilities_role_name_incompatible_with"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_name: Mapped[str] = mapped_column(String(80), ForeignKey("roles.name"), nullable=False)
    incompatible_with: Mapped[str] = mapped_column(String(80), ForeignKey("roles.name"), nullable=False)

    role: Mapped[Role] = relationship(back_populates="incompatible_roles", foreign_keys=[role_name])

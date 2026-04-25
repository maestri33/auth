from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from auth.database import Base


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Role(Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_transitory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    transitions_to: Mapped[str | None] = mapped_column(String(80), ForeignKey("roles.name"), nullable=True)
    requires_role: Mapped[str | None] = mapped_column(String(80), ForeignKey("roles.name"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    incompatible_roles: Mapped[list["RoleIncompatibility"]] = relationship(
        back_populates="role",
        foreign_keys="RoleIncompatibility.role_name",
        cascade="all, delete-orphan",
    )


class RoleIncompatibility(Base):
    __tablename__ = "role_incompatibilities"
    __table_args__ = (UniqueConstraint("role_name", "incompatible_with", name="uq_role_incompatible"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_name: Mapped[str] = mapped_column(String(80), ForeignKey("roles.name"), nullable=False)
    incompatible_with: Mapped[str] = mapped_column(String(80), ForeignKey("roles.name"), nullable=False)

    role: Mapped[Role] = relationship(back_populates="incompatible_roles", foreign_keys=[role_name])


class User(Base):
    __tablename__ = "users"

    external_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    otps: Mapped[list["OtpChallenge"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("external_id", "role_name", name="uq_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.external_id"), nullable=False)
    role_name: Mapped[str] = mapped_column(String(80), ForeignKey("roles.name"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="roles")


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.external_id"), nullable=False, index=True)
    otp_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="otps")

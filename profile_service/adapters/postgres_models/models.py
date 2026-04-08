from datetime import UTC, datetime
from typing import final

import sqlalchemy as sa
from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from profile_service.domain.photo import Photo
from profile_service.domain.profile import Gender, Profile


class Base(DeclarativeBase):
    pass


@final
class UserORM(Base):
    __tablename__: str = "users"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )

    __table_args__: tuple[sa.UniqueConstraint] = (sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),)

    profile: Mapped["ProfileORM | None"] = relationship(back_populates="user", uselist=False)


@final
class ProfileORM(Base):
    __tablename__: str = "profiles"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    bio: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    age: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    gender: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)
    city: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    location: Mapped[WKBElement | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=True,
    )
    ai_quality_score: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        default=lambda: datetime.now(UTC),
    )

    __table_args__: tuple[sa.Index] = (sa.Index("ix_profiles_user_id", "user_id", unique=True),)

    user: Mapped[UserORM] = relationship(back_populates="profile")
    photos: Mapped[list["PhotoORM"]] = relationship(back_populates="profile")

    def to_domain(self, telegram_id: int) -> Profile:
        lat: float | None = None
        lon: float | None = None
        if self.location is not None:
            pt = to_shape(self.location)
            lon, lat = float(pt.x), float(pt.y)
        return Profile(
            id=self.id,
            user_id=self.user_id,
            telegram_id=telegram_id,
            name=self.name,
            bio=self.bio,
            age=self.age,
            gender=Gender(self.gender) if self.gender else None,
            city=self.city,
            latitude=lat,
            longitude=lon,
            ai_quality_score=self.ai_quality_score,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


@final
class PhotoORM(Base):
    __tablename__: str = "photos"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        sa.BigInteger(),
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    minio_key: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, server_default=sa.true())
    is_nsfw: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, server_default=sa.false())
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        default=lambda: datetime.now(UTC),
    )

    __table_args__: tuple[sa.Index] = (sa.Index("ix_photos_profile_id", "profile_id"),)

    profile: Mapped[ProfileORM] = relationship(back_populates="photos")

    def to_domain(self) -> Photo:
        return Photo(
            id=self.id,
            profile_id=self.profile_id,
            minio_key=self.minio_key,
            is_active=self.is_active,
            is_nsfw=self.is_nsfw,
            created_at=self.created_at,
        )


@final
class PreferenceORM(Base):
    __tablename__: str = "preferences"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        sa.BigInteger(),
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    min_age: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    max_age: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    gender: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)
    max_distance_km: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)

    __table_args__: tuple[sa.UniqueConstraint] = (sa.UniqueConstraint("profile_id", name="uq_preferences_profile_id"),)

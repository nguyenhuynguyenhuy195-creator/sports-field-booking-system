from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .user import timestamp_type, utc_now


class MediaImage(db.Model):
    """Stored image metadata for exactly one Venue or Field."""

    __tablename__ = "media_images"
    __table_args__ = (
        db.CheckConstraint(
            "(venue_id IS NOT NULL AND field_id IS NULL) OR "
            "(venue_id IS NULL AND field_id IS NOT NULL)",
            name="ck_media_images_single_parent",
        ),
        db.CheckConstraint(
            "size_bytes > 0",
            name="ck_media_images_size_positive",
        ),
        db.Index("ix_media_images_venue_created", "venue_id", "created_at"),
        db.Index("ix_media_images_field_created", "field_id", "created_at"),
        db.Index(
            "uq_media_images_venue_cover",
            "venue_id",
            unique=True,
            sqlite_where=db.text(
                "is_cover = 1 AND venue_id IS NOT NULL"
            ),
            mssql_where=db.text(
                "is_cover = 1 AND venue_id IS NOT NULL"
            ),
        ),
        db.Index(
            "uq_media_images_field_cover",
            "field_id",
            unique=True,
            sqlite_where=db.text(
                "is_cover = 1 AND field_id IS NOT NULL"
            ),
            mssql_where=db.text(
                "is_cover = 1 AND field_id IS NOT NULL"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    venue_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=True,
    )
    field_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("fields.id", ondelete="CASCADE"),
        nullable=True,
    )
    storage_path: Mapped[str] = mapped_column(
        db.String(255),
        nullable=False,
        unique=True,
    )
    original_filename: Mapped[str] = mapped_column(
        db.Unicode(255),
        nullable=False,
    )
    content_type: Mapped[str] = mapped_column(db.String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(db.Integer, nullable=False)
    is_cover: Mapped[bool] = mapped_column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
    )
    created_at: Mapped[datetime] = mapped_column(
        timestamp_type,
        nullable=False,
        default=utc_now,
    )

    venue: Mapped["Venue | None"] = relationship(back_populates="media_images")
    field: Mapped["Field | None"] = relationship(back_populates="media_images")

    def __repr__(self) -> str:
        return (
            f"<MediaImage id={self.id!r} venue_id={self.venue_id!r} "
            f"field_id={self.field_id!r} is_cover={self.is_cover!r}>"
        )

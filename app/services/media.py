from __future__ import annotations

from pathlib import Path, PurePosixPath
from uuid import uuid4

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Field, FieldStatus, MediaImage, Venue, VenueStatus
from app.services.field import (
    FieldNotFoundError,
    FieldPermissionError,
    get_owner_field,
)
from app.services.venue import (
    VenueNotFoundError,
    VenuePermissionError,
    get_owner_venue,
)


class MediaError(ValueError):
    """Base error for image management."""


class MediaValidationError(MediaError):
    """Raised when an uploaded file is not an accepted image."""


class MediaNotFoundError(MediaError):
    """Raised when an image or its scoped parent does not exist."""


class MediaPermissionError(MediaError):
    """Raised when an owner manages media outside their venues."""


ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
CANONICAL_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def upload_venue_image(
    *,
    owner_id: int,
    venue_id: int,
    file: FileStorage,
) -> MediaImage:
    venue = _get_owned_venue(venue_id=venue_id, owner_id=owner_id)
    return _store_image(file=file, venue=venue)


def upload_field_image(
    *,
    owner_id: int,
    venue_id: int,
    field_id: int,
    file: FileStorage,
) -> MediaImage:
    field = _get_owned_field(
        venue_id=venue_id,
        field_id=field_id,
        owner_id=owner_id,
    )
    return _store_image(file=file, field=field)


def set_venue_cover(
    *, owner_id: int, venue_id: int, media_id: int
) -> MediaImage:
    _get_owned_venue(venue_id=venue_id, owner_id=owner_id)
    image = _get_scoped_image(media_id=media_id, venue_id=venue_id)
    return _set_cover(image)


def set_field_cover(
    *,
    owner_id: int,
    venue_id: int,
    field_id: int,
    media_id: int,
) -> MediaImage:
    _get_owned_field(
        venue_id=venue_id,
        field_id=field_id,
        owner_id=owner_id,
    )
    image = _get_scoped_image(
        media_id=media_id,
        field_id=field_id,
    )
    return _set_cover(image)


def delete_venue_image(
    *, owner_id: int, venue_id: int, media_id: int
) -> None:
    _get_owned_venue(venue_id=venue_id, owner_id=owner_id)
    image = _get_scoped_image(media_id=media_id, venue_id=venue_id)
    _delete_image(image)


def delete_field_image(
    *,
    owner_id: int,
    venue_id: int,
    field_id: int,
    media_id: int,
) -> None:
    _get_owned_field(
        venue_id=venue_id,
        field_id=field_id,
        owner_id=owner_id,
    )
    image = _get_scoped_image(
        media_id=media_id,
        field_id=field_id,
    )
    _delete_image(image)


def get_visible_image(
    *, media_id: int, viewer_owner_id: int | None = None
) -> MediaImage:
    image = db.session.scalar(
        db.select(MediaImage)
        .options(
            joinedload(MediaImage.venue),
            joinedload(MediaImage.field).joinedload(Field.venue),
        )
        .where(MediaImage.id == media_id)
    )
    if image is None:
        raise MediaNotFoundError("Không tìm thấy ảnh.")

    if image.venue is not None:
        is_owner = image.venue.owner_id == viewer_owner_id
        is_public = image.venue.status == VenueStatus.ACTIVE.value
    else:
        is_owner = image.field.venue.owner_id == viewer_owner_id
        is_public = (
            image.field.venue.status == VenueStatus.ACTIVE.value
            and image.field.status == FieldStatus.ACTIVE.value
        )
    if not (is_owner or is_public):
        raise MediaNotFoundError("Không tìm thấy ảnh.")
    return image


def resolve_media_path(image: MediaImage) -> Path:
    root = Path(current_app.config["MEDIA_ROOT"]).resolve()
    relative = PurePosixPath(image.storage_path)
    candidate = root.joinpath(*relative.parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise MediaNotFoundError("Đường dẫn ảnh không hợp lệ.") from exc
    return candidate


def _store_image(
    *,
    file: FileStorage,
    venue: Venue | None = None,
    field: Field | None = None,
) -> MediaImage:
    original_filename, content_type, content = _validate_image(file)
    parent_kind = "venues" if venue is not None else "fields"
    parent_id = venue.id if venue is not None else field.id
    extension = CANONICAL_EXTENSION[content_type]
    storage_path = (
        PurePosixPath(parent_kind)
        / str(parent_id)
        / f"{uuid4().hex}{extension}"
    )

    root = Path(current_app.config["MEDIA_ROOT"]).resolve()
    destination = root.joinpath(*storage_path.parts).resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise MediaError("Không thể tạo đường dẫn lưu ảnh an toàn.") from exc

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    except OSError as exc:
        raise MediaError("Không thể lưu ảnh lúc này. Vui lòng thử lại.") from exc

    try:
        parent_filter = (
            MediaImage.venue_id == venue.id
            if venue is not None
            else MediaImage.field_id == field.id
        )
        has_image = db.session.scalar(
            db.select(MediaImage.id).where(parent_filter).limit(1)
        )
        image = MediaImage(
            venue_id=venue.id if venue is not None else None,
            field_id=field.id if field is not None else None,
            storage_path=storage_path.as_posix(),
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=len(content),
            is_cover=has_image is None,
        )
        db.session.add(image)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            current_app.logger.exception(
                "Failed to remove media file after database rollback: %s",
                destination,
            )
        raise MediaError("Không thể lưu thông tin ảnh lúc này.") from exc
    return image


def _validate_image(file: FileStorage) -> tuple[str, str, bytes]:
    raw_filename = (file.filename or "").strip()
    safe_filename = secure_filename(raw_filename)
    if not safe_filename:
        raise MediaValidationError("Tên tệp ảnh không hợp lệ.")

    extension = Path(safe_filename).suffix.lower()
    expected_type = ALLOWED_IMAGE_EXTENSIONS.get(extension)
    if expected_type is None:
        raise MediaValidationError(
            "Chỉ chấp nhận ảnh JPG, PNG hoặc WebP."
        )

    max_bytes = int(current_app.config["MEDIA_MAX_BYTES"])
    content = file.stream.read(max_bytes + 1)
    if not content:
        raise MediaValidationError("Tệp ảnh đang trống.")
    if len(content) > max_bytes:
        raise MediaValidationError(
            f"Ảnh không được vượt quá {max_bytes // (1024 * 1024)} MB."
        )

    detected_type = _detect_content_type(content)
    if detected_type is None or detected_type != expected_type:
        raise MediaValidationError(
            "Nội dung tệp không khớp với định dạng ảnh được hỗ trợ."
        )
    declared_type = (file.mimetype or "").lower()
    if declared_type not in {detected_type, "image/jpg"}:
        raise MediaValidationError("Loại nội dung của tệp ảnh không hợp lệ.")
    return safe_filename, detected_type, content


def _detect_content_type(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if (
        len(content) >= 4
        and content.startswith(b"\xff\xd8\xff")
        and content.endswith(b"\xff\xd9")
    ):
        return "image/jpeg"
    if (
        len(content) >= 12
        and content.startswith(b"RIFF")
        and content[8:12] == b"WEBP"
    ):
        return "image/webp"
    return None


def _get_owned_venue(*, venue_id: int, owner_id: int) -> Venue:
    try:
        return get_owner_venue(venue_id=venue_id, owner_id=owner_id)
    except VenueNotFoundError as exc:
        raise MediaNotFoundError(str(exc)) from exc
    except VenuePermissionError as exc:
        raise MediaPermissionError(str(exc)) from exc


def _get_owned_field(
    *, venue_id: int, field_id: int, owner_id: int
) -> Field:
    try:
        field = get_owner_field(field_id=field_id, owner_id=owner_id)
    except FieldNotFoundError as exc:
        raise MediaNotFoundError(str(exc)) from exc
    except FieldPermissionError as exc:
        raise MediaPermissionError(str(exc)) from exc
    if field.venue_id != venue_id:
        raise MediaNotFoundError("Không tìm thấy sân trong cơ sở này.")
    return field


def _get_scoped_image(
    *,
    media_id: int,
    venue_id: int | None = None,
    field_id: int | None = None,
) -> MediaImage:
    conditions = [MediaImage.id == media_id]
    if venue_id is not None:
        conditions.extend(
            [MediaImage.venue_id == venue_id, MediaImage.field_id.is_(None)]
        )
    else:
        conditions.extend(
            [MediaImage.field_id == field_id, MediaImage.venue_id.is_(None)]
        )
    image = db.session.scalar(
        db.select(MediaImage).where(*conditions).with_for_update()
    )
    if image is None:
        raise MediaNotFoundError("Không tìm thấy ảnh trong mục này.")
    return image


def _set_cover(image: MediaImage) -> MediaImage:
    if image.is_cover:
        return image
    parent_filter = (
        MediaImage.venue_id == image.venue_id
        if image.venue_id is not None
        else MediaImage.field_id == image.field_id
    )
    current_covers = list(
        db.session.scalars(
            db.select(MediaImage)
            .where(parent_filter, MediaImage.is_cover.is_(True))
            .with_for_update()
        )
    )
    for current_cover in current_covers:
        current_cover.is_cover = False
    try:
        db.session.flush()
        image.is_cover = True
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise MediaError("Không thể đổi ảnh đại diện lúc này.") from exc
    return image


def _delete_image(image: MediaImage) -> None:
    path = resolve_media_path(image)
    parent_filter = (
        MediaImage.venue_id == image.venue_id
        if image.venue_id is not None
        else MediaImage.field_id == image.field_id
    )
    try:
        if image.is_cover:
            image.is_cover = False
            db.session.flush()
            fallback = db.session.scalar(
                db.select(MediaImage)
                .where(parent_filter, MediaImage.id != image.id)
                .order_by(MediaImage.created_at.asc(), MediaImage.id.asc())
                .limit(1)
                .with_for_update()
            )
            if fallback is not None:
                fallback.is_cover = True
        db.session.delete(image)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise MediaError("Không thể xóa ảnh lúc này.") from exc

    try:
        path.unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning(
            "Media metadata deleted but file could not be removed: %s",
            path,
        )

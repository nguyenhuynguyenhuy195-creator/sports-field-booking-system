from dataclasses import dataclass
from datetime import time
from io import BytesIO
from pathlib import Path

import pytest
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage

import app.services.media as media_service
from app.extensions import db
from app.models import (
    Field,
    FieldStatus,
    FieldTypeCode,
    MediaImage,
    User,
    UserRole,
    Venue,
    VenueStatus,
)
from app.services import MediaError, create_field, create_venue, register_user


PASSWORD = "MatKhauAnToan123"
PNG_BYTES = b"\x89PNG\r\n\x1a\nowner-media-test"


@dataclass(frozen=True)
class CreatedUser:
    id: int
    email: str


def create_user(app, *, email: str, role: UserRole) -> CreatedUser:
    with app.app_context():
        user = register_user(
            full_name="Nguyễn Văn Media",
            email=email,
            phone="0901234567",
            password=PASSWORD,
        )
        user.role = role.value
        db.session.commit()
        return CreatedUser(id=user.id, email=user.email)


def login(client, *, email: str) -> None:
    response = client.post(
        "/auth/login",
        data={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 302


def create_venue_for_owner(
    app,
    *,
    owner_id: int,
    name: str,
    status: VenueStatus = VenueStatus.PENDING,
) -> int:
    with app.app_context():
        owner = db.session.get(User, owner_id)
        venue = create_venue(
            owner=owner,
            name=name,
            address="123 Nguyễn Hữu Thọ",
            province_code="79",
            ward_code="27475",
            phone="0909876543",
            description=None,
            opening_time=time(6, 0),
            closing_time=time(22, 0),
        )
        venue.status = status.value
        db.session.commit()
        return venue.id


def create_field_for_owner(
    app,
    *,
    owner_id: int,
    venue_id: int,
    name: str,
    status: FieldStatus = FieldStatus.INACTIVE,
) -> int:
    with app.app_context():
        owner = db.session.get(User, owner_id)
        field = create_field(
            owner=owner,
            venue_id=venue_id,
            name=name,
            field_type=FieldTypeCode.FOOTBALL_7.value,
            surface_type="Cỏ nhân tạo",
            capacity=14,
        )
        field.status = status.value
        db.session.commit()
        return field.id


def upload_image(
    client,
    url: str,
    *,
    filename: str = "san.png",
    content: bytes = PNG_BYTES,
    content_type: str = "image/png",
):
    return client.post(
        url,
        data={"image": (BytesIO(content), filename, content_type)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def test_venue_media_lifecycle_cover_fallback_and_placeholder(app, client):
    owner = create_user(
        app,
        email="venue-media-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(
        app,
        owner_id=owner.id,
        name="Cơ sở ảnh",
    )
    login(client, email=owner.email)

    edit_url = f"/owner/venues/{venue_id}/edit"
    response = client.get(edit_url)
    assert response.status_code == 200
    assert "Chưa có hình ảnh" in response.get_data(as_text=True)

    response = upload_image(
        client,
        f"/owner/venues/{venue_id}/media",
        filename="anh-bia.png",
    )
    assert response.status_code == 200
    assert "Đã tải ảnh cơ sở lên." in response.get_data(as_text=True)

    response = upload_image(
        client,
        f"/owner/venues/{venue_id}/media",
        filename="anh-bia.png",
    )
    assert response.status_code == 200

    with app.app_context():
        images = list(
            db.session.scalars(
                db.select(MediaImage)
                .where(MediaImage.venue_id == venue_id)
                .order_by(MediaImage.id)
            )
        )
        assert len(images) == 2
        assert [image.is_cover for image in images] == [True, False]
        assert len({image.storage_path for image in images}) == 2
        assert all(".." not in image.storage_path for image in images)
        assert all(
            (Path(app.config["MEDIA_ROOT"]) / image.storage_path).is_file()
            for image in images
        )
        first_id, second_id = images[0].id, images[1].id
        first_path = Path(app.config["MEDIA_ROOT"]) / images[0].storage_path

    response = client.post(
        f"/owner/venues/{venue_id}/media/{second_id}/cover",
        follow_redirects=True,
    )
    assert "Đã đổi ảnh đại diện của cơ sở." in response.get_data(as_text=True)
    with app.app_context():
        images = list(
            db.session.scalars(
                db.select(MediaImage)
                .where(MediaImage.venue_id == venue_id)
                .order_by(MediaImage.id)
            )
        )
        assert [image.is_cover for image in images] == [False, True]

    response = client.post(
        f"/owner/venues/{venue_id}/media/{first_id}/delete",
        follow_redirects=True,
    )
    assert "Đã xóa ảnh cơ sở." in response.get_data(as_text=True)
    assert not first_path.exists()
    with app.app_context():
        remaining = db.session.get(MediaImage, second_id)
        assert remaining is not None and remaining.is_cover

    upload_image(
        client,
        f"/owner/venues/{venue_id}/media",
        filename="anh-thay-the.png",
    )
    with app.app_context():
        fallback_id = db.session.scalar(
            db.select(MediaImage.id).where(
                MediaImage.venue_id == venue_id,
                MediaImage.id != second_id,
            )
        )

    client.post(
        f"/owner/venues/{venue_id}/media/{second_id}/delete",
        follow_redirects=True,
    )
    with app.app_context():
        fallback = db.session.get(MediaImage, fallback_id)
        assert fallback is not None and fallback.is_cover

    response = client.post(
        f"/owner/venues/{venue_id}/media/{fallback_id}/delete",
        follow_redirects=True,
    )
    assert "Chưa có hình ảnh" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count(MediaImage.id)).where(
                MediaImage.venue_id == venue_id
            )
        ) == 0


def test_upload_rejects_invalid_extension_content_and_oversized_image(
    app, client
):
    owner = create_user(
        app,
        email="invalid-media-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(
        app,
        owner_id=owner.id,
        name="Cơ sở kiểm tra ảnh",
    )
    login(client, email=owner.email)
    upload_url = f"/owner/venues/{venue_id}/media"

    response = upload_image(client, upload_url, filename="anh.txt")
    assert "Chỉ chấp nhận ảnh JPG, PNG hoặc WebP." in response.get_data(
        as_text=True
    )

    response = upload_image(
        client,
        upload_url,
        filename="gia-mao.png",
        content=b"not-an-image",
    )
    assert "Nội dung tệp không khớp" in response.get_data(as_text=True)

    response = upload_image(
        client,
        upload_url,
        filename="sai-mime.png",
        content_type="text/plain",
    )
    assert "Loại nội dung của tệp ảnh không hợp lệ." in response.get_data(
        as_text=True
    )

    oversized = b"\x89PNG\r\n\x1a\n" + b"x" * int(
        app.config["MEDIA_MAX_BYTES"]
    )
    response = upload_image(
        client,
        upload_url,
        filename="qua-lon.png",
        content=oversized,
    )
    assert "Ảnh không được vượt quá 5 MB." in response.get_data(as_text=True)

    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(MediaImage.id))) == 0


def test_field_media_gallery_and_public_rendering(app, client):
    owner = create_user(
        app,
        email="field-media-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(
        app,
        owner_id=owner.id,
        name="Cơ sở công khai",
        status=VenueStatus.ACTIVE,
    )
    field_id = create_field_for_owner(
        app,
        owner_id=owner.id,
        venue_id=venue_id,
        name="Sân công khai",
        status=FieldStatus.ACTIVE,
    )
    login(client, email=owner.email)

    response = client.get(
        f"/owner/venues/{venue_id}/fields/{field_id}/edit"
    )
    assert "Chưa có hình ảnh" in response.get_data(as_text=True)
    response = client.get(f"/venues/{venue_id}")
    empty_public_html = response.get_data(as_text=True)
    assert "Cơ sở chưa cập nhật hình ảnh." in empty_public_html
    assert "Chưa có ảnh sân" in empty_public_html

    upload_image(client, f"/owner/venues/{venue_id}/media")
    upload_image(
        client,
        f"/owner/venues/{venue_id}/media",
        filename="venue-gallery.png",
    )
    field_upload_url = (
        f"/owner/venues/{venue_id}/fields/{field_id}/media"
    )
    upload_image(client, field_upload_url, filename="field-cover.png")
    upload_image(client, field_upload_url, filename="field-gallery.png")

    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        field = db.session.get(Field, field_id)
        venue_image_ids = [image.id for image in venue.media_images]
        field_image_ids = [image.id for image in field.media_images]
        assert sum(image.is_cover for image in venue.media_images) == 1
        assert sum(image.is_cover for image in field.media_images) == 1

    client.post("/auth/logout")
    response = client.get("/venues")
    index_html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert f'/media/{venue_image_ids[0]}' in index_html

    response = client.get(f"/venues/{venue_id}")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "HÌNH ẢNH CƠ SỞ" in html
    for image_id in venue_image_ids + field_image_ids:
        assert f'/media/{image_id}' in html

    response = client.get(f"/media/{field_image_ids[0]}")
    assert response.status_code == 200
    assert response.content_type == "image/png"
    assert response.headers["X-Content-Type-Options"] == "nosniff"

    login(client, email=owner.email)
    response = client.post(
        f"/owner/venues/{venue_id}/fields/{field_id}/media/"
        f"{field_image_ids[1]}/cover",
        follow_redirects=True,
    )
    assert "Đã đổi ảnh đại diện của sân." in response.get_data(as_text=True)
    client.post(
        f"/owner/venues/{venue_id}/fields/{field_id}/media/"
        f"{field_image_ids[1]}/delete",
        follow_redirects=True,
    )
    with app.app_context():
        fallback = db.session.get(MediaImage, field_image_ids[0])
        assert fallback is not None and fallback.is_cover


def test_media_permissions_and_nested_scope_do_not_leak(app, client):
    owner = create_user(
        app,
        email="media-owner-one@example.com",
        role=UserRole.OWNER,
    )
    other_owner = create_user(
        app,
        email="media-owner-two@example.com",
        role=UserRole.OWNER,
    )
    player = create_user(
        app,
        email="media-player@example.com",
        role=UserRole.USER,
    )
    admin = create_user(
        app,
        email="media-admin@example.com",
        role=UserRole.ADMIN,
    )
    venue_id = create_venue_for_owner(
        app, owner_id=owner.id, name="Cơ sở Owner 1"
    )
    second_owned_venue_id = create_venue_for_owner(
        app, owner_id=owner.id, name="Cơ sở Owner 1 khác"
    )
    field_id = create_field_for_owner(
        app,
        owner_id=owner.id,
        venue_id=venue_id,
        name="Sân Owner 1",
    )
    mismatched_field_id = create_field_for_owner(
        app,
        owner_id=owner.id,
        venue_id=second_owned_venue_id,
        name="Sân khác Venue",
    )
    foreign_venue_id = create_venue_for_owner(
        app, owner_id=other_owner.id, name="Cơ sở Owner 2"
    )
    foreign_field_id = create_field_for_owner(
        app,
        owner_id=other_owner.id,
        venue_id=foreign_venue_id,
        name="Sân Owner 2",
    )

    assert client.post(f"/owner/venues/{venue_id}/media").status_code == 302
    for account in (player, admin):
        login(client, email=account.email)
        assert client.post(f"/owner/venues/{venue_id}/media").status_code == 403
        client.post("/auth/logout")

    login(client, email=owner.email)
    assert upload_image(
        client,
        f"/owner/venues/{foreign_venue_id}/media",
    ).status_code == 403
    assert upload_image(
        client,
        f"/owner/venues/{foreign_venue_id}/fields/{foreign_field_id}/media",
    ).status_code == 403
    assert upload_image(
        client,
        f"/owner/venues/{venue_id}/fields/{mismatched_field_id}/media",
    ).status_code == 404

    upload_image(client, f"/owner/venues/{venue_id}/media")
    upload_image(
        client,
        f"/owner/venues/{venue_id}/fields/{field_id}/media",
    )
    with app.app_context():
        venue_media_id = db.session.scalar(
            db.select(MediaImage.id).where(MediaImage.venue_id == venue_id)
        )
        field_media_id = db.session.scalar(
            db.select(MediaImage.id).where(MediaImage.field_id == field_id)
        )

    assert client.post(
        f"/owner/venues/{venue_id}/media/{field_media_id}/cover"
    ).status_code == 404
    assert client.post(
        f"/owner/venues/{venue_id}/fields/{field_id}/media/"
        f"{venue_media_id}/delete"
    ).status_code == 404

    client.post("/auth/logout")
    login(client, email=other_owner.email)
    upload_image(client, f"/owner/venues/{foreign_venue_id}/media")
    with app.app_context():
        foreign_media = db.session.scalar(
            db.select(MediaImage).where(
                MediaImage.venue_id == foreign_venue_id
            )
        )
        foreign_media_id = foreign_media.id
        foreign_path = Path(app.config["MEDIA_ROOT"]) / foreign_media.storage_path
    client.post("/auth/logout")
    login(client, email=owner.email)
    assert client.post(
        f"/owner/venues/{foreign_venue_id}/media/{foreign_media_id}/delete"
    ).status_code == 403
    with app.app_context():
        assert db.session.get(MediaImage, foreign_media_id) is not None
        assert foreign_path.is_file()


def test_non_public_media_is_visible_only_to_its_owner(app, client):
    owner = create_user(
        app,
        email="private-media-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(
        app,
        owner_id=owner.id,
        name="Cơ sở chưa duyệt",
    )
    login(client, email=owner.email)
    upload_image(client, f"/owner/venues/{venue_id}/media")
    with app.app_context():
        media_id = db.session.scalar(
            db.select(MediaImage.id).where(MediaImage.venue_id == venue_id)
        )

    assert client.get(f"/media/{media_id}").status_code == 200
    client.post("/auth/logout")
    assert client.get(f"/media/{media_id}").status_code == 404


def test_upload_db_failure_after_file_write_removes_orphan(
    app, monkeypatch
):
    owner = create_user(
        app,
        email="media-db-failure@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(
        app,
        owner_id=owner.id,
        name="Cơ sở lỗi DB",
    )

    with app.app_context():
        venue = db.session.get(Venue, venue_id)

        def fail_scalar(*_args, **_kwargs):
            raise SQLAlchemyError("forced media query failure")

        with monkeypatch.context() as scoped_patch:
            scoped_patch.setattr(db.session, "scalar", fail_scalar)
            with pytest.raises(MediaError):
                media_service._store_image(
                    venue=venue,
                    file=FileStorage(
                        stream=BytesIO(PNG_BYTES),
                        filename="rollback.png",
                        content_type="image/png",
                    ),
                )

        media_root = Path(app.config["MEDIA_ROOT"])
        assert not list(media_root.rglob("*.*"))
        assert db.session.scalar(
            db.select(db.func.count(MediaImage.id))
        ) == 0


def test_delete_db_failure_keeps_file_and_database_state(
    app, monkeypatch
):
    owner = create_user(
        app,
        email="media-delete-failure@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(
        app,
        owner_id=owner.id,
        name="Cơ sở rollback xóa",
    )
    with app.app_context():
        first = media_service.upload_venue_image(
            owner_id=owner.id,
            venue_id=venue_id,
            file=FileStorage(
                stream=BytesIO(PNG_BYTES),
                filename="cover.png",
                content_type="image/png",
            ),
        )
        media_service.upload_venue_image(
            owner_id=owner.id,
            venue_id=venue_id,
            file=FileStorage(
                stream=BytesIO(PNG_BYTES),
                filename="gallery.png",
                content_type="image/png",
            ),
        )
        first_id = first.id
        first_path = Path(app.config["MEDIA_ROOT"]) / first.storage_path

        def fail_commit():
            raise SQLAlchemyError("forced delete failure")

        with monkeypatch.context() as scoped_patch:
            scoped_patch.setattr(db.session, "commit", fail_commit)
            with pytest.raises(MediaError):
                media_service.delete_venue_image(
                    owner_id=owner.id,
                    venue_id=venue_id,
                    media_id=first_id,
                )

        remaining = db.session.get(MediaImage, first_id)
        assert remaining is not None and remaining.is_cover
        assert first_path.is_file()
        assert db.session.scalar(
            db.select(db.func.count(MediaImage.id)).where(
                MediaImage.venue_id == venue_id
            )
        ) == 2


def test_set_cover_db_failure_rolls_back_without_touching_files(
    app, monkeypatch
):
    owner = create_user(
        app,
        email="media-cover-failure@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(
        app,
        owner_id=owner.id,
        name="Cơ sở rollback cover",
    )
    with app.app_context():
        first = media_service.upload_venue_image(
            owner_id=owner.id,
            venue_id=venue_id,
            file=FileStorage(
                stream=BytesIO(PNG_BYTES),
                filename="first.png",
                content_type="image/png",
            ),
        )
        second = media_service.upload_venue_image(
            owner_id=owner.id,
            venue_id=venue_id,
            file=FileStorage(
                stream=BytesIO(PNG_BYTES),
                filename="second.png",
                content_type="image/png",
            ),
        )
        paths = [
            Path(app.config["MEDIA_ROOT"]) / image.storage_path
            for image in (first, second)
        ]

        def fail_commit():
            raise SQLAlchemyError("forced cover failure")

        with monkeypatch.context() as scoped_patch:
            scoped_patch.setattr(db.session, "commit", fail_commit)
            with pytest.raises(MediaError):
                media_service.set_venue_cover(
                    owner_id=owner.id,
                    venue_id=venue_id,
                    media_id=second.id,
                )

        covers = list(
            db.session.scalars(
                db.select(MediaImage)
                .where(MediaImage.venue_id == venue_id)
                .order_by(MediaImage.id)
            )
        )
        assert [image.is_cover for image in covers] == [True, False]
        assert all(path.is_file() for path in paths)


def test_missing_physical_file_returns_404_instead_of_500(app, client):
    owner = create_user(
        app,
        email="media-missing-file@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(
        app,
        owner_id=owner.id,
        name="Cơ sở thiếu file",
    )
    login(client, email=owner.email)
    upload_image(client, f"/owner/venues/{venue_id}/media")
    with app.app_context():
        image = db.session.scalar(
            db.select(MediaImage).where(MediaImage.venue_id == venue_id)
        )
        path = Path(app.config["MEDIA_ROOT"]) / image.storage_path
        media_id = image.id
        path.unlink()

    response = client.get(f"/media/{media_id}")
    assert response.status_code == 404

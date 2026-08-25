from __future__ import annotations

from enum import Enum

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class WardType(str, Enum):
    PHUONG = "PHUONG"
    XA = "XA"
    DAC_KHU = "DAC_KHU"


WARD_TYPE_LABELS = {
    WardType.PHUONG.value: "Phường",
    WardType.XA.value: "Xã",
    WardType.DAC_KHU.value: "Đặc khu",
}


class Province(db.Model):
    __tablename__ = "provinces"
    __table_args__ = (
        db.UniqueConstraint("name", name="uq_provinces_name"),
    )

    code: Mapped[str] = mapped_column(db.String(2), primary_key=True)
    name: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)

    wards: Mapped[list["Ward"]] = relationship(
        back_populates="province",
        order_by="Ward.name",
    )

    def __repr__(self) -> str:
        return f"<Province code={self.code!r} name={self.name!r}>"


class Ward(db.Model):
    __tablename__ = "wards"
    __table_args__ = (
        db.CheckConstraint(
            "type IN ('PHUONG', 'XA', 'DAC_KHU')",
            name="ck_wards_type",
        ),
        db.Index("ix_wards_province_name", "province_code", "name"),
    )

    code: Mapped[str] = mapped_column(db.String(5), primary_key=True)
    province_code: Mapped[str] = mapped_column(
        db.ForeignKey("provinces.code"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    type: Mapped[str] = mapped_column(db.String(20), nullable=False)

    province: Mapped[Province] = relationship(back_populates="wards")

    @property
    def type_label(self) -> str:
        return WARD_TYPE_LABELS[self.type]

    @property
    def full_name(self) -> str:
        return f"{self.type_label} {self.name}"

    def __repr__(self) -> str:
        return (
            f"<Ward code={self.code!r} province_code={self.province_code!r} "
            f"name={self.name!r}>"
        )

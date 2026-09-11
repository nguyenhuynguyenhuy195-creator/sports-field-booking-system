from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable
from urllib.parse import quote_plus

from flask import current_app


class VnpayError(RuntimeError):
    """Raised for VNPAY protocol-level failures (config, amount, signature)."""


class VnpayConfigurationError(VnpayError):
    """Raised when Sandbox credentials or gateway URLs are incomplete."""


class VnpaySignatureError(VnpayError):
    """Raised when a callback signature is missing or invalid."""


class VnpayAmountError(VnpayError):
    """Raised when an amount cannot be safely converted to vnp_Amount."""


_EXCLUDED_SIGN_FIELDS = {"vnp_SecureHash", "vnp_SecureHashType"}


@dataclass(frozen=True)
class VnpayCallbackFields:
    """Read-only, parsed view of a VNPAY Return/IPN callback.

    This is a pure protocol-level parsing helper: it carries no opinion about
    Payment/Booking/Contribution state. Step 3 decides what to do with it.
    """

    is_success: bool
    response_code: str | None
    transaction_status: str | None
    txn_ref: str | None
    amount_vnd: Decimal | None
    transaction_no: str | None
    bank_code: str | None
    pay_date: str | None
    order_info: str | None


class VnpayClient:
    """Protocol-only VNPAY Sandbox client.

    Builds payment URLs and verifies callback signatures per the VNPAY PAY
    2.1.0 integration guide. Contains no Booking/Contribution/Match/DB logic.
    """

    def __init__(
        self,
        *,
        tmn_code: str,
        hash_secret: str,
        payment_url: str,
        api_url: str = "",
        timeout_seconds: int = 30,
        transport: Callable[..., dict] | None = None,
    ) -> None:
        if not tmn_code or not hash_secret or not payment_url:
            raise VnpayConfigurationError(
                "Thiếu thông tin kết nối VNPAY thử nghiệm."
            )
        self.tmn_code = tmn_code
        self._hash_secret = hash_secret
        self.payment_url = payment_url.rstrip("?")
        self.api_url = api_url
        self.timeout_seconds = max(int(timeout_seconds), 30)
        self._transport = transport

    def __repr__(self) -> str:
        # Never include _hash_secret in repr/log output.
        return f"<VnpayClient tmn_code={self.tmn_code!r}>"

    @classmethod
    def from_app_config(cls) -> "VnpayClient":
        if not current_app.config.get("VNPAY_ENABLED"):
            raise VnpayConfigurationError(
                "Thanh toán VNPAY thử nghiệm chưa được bật."
            )
        return cls(
            tmn_code=current_app.config.get("VNPAY_TMN_CODE", ""),
            hash_secret=current_app.config.get("VNPAY_HASH_SECRET", ""),
            payment_url=current_app.config.get("VNPAY_PAYMENT_URL", ""),
            api_url=current_app.config.get("VNPAY_API_URL", ""),
            timeout_seconds=current_app.config.get("VNPAY_TIMEOUT_SECONDS", 30),
        )

    def build_payment_url(
        self,
        *,
        order_id: str,
        amount: Decimal | int | str,
        order_info: str,
        return_url: str,
        ip_addr: str,
        create_date: str,
        order_type: str = "other",
        locale: str = "vn",
        version: str = "2.1.0",
        curr_code: str = "VND",
        expire_date: str | None = None,
        bank_code: str | None = None,
    ) -> str:
        """Build a full VNPAY checkout URL (payment_url + signed query string).

        Pass bank_code="VNPAYQR" to force the VNPAY-QR flow. PaymentMethod
        stored on our side stays VNPAY_GATEWAY regardless of bank_code — this
        is purely a VNPAY-side routing parameter, not a new payment method.
        """
        fields: dict[str, str] = {
            "vnp_Version": version,
            "vnp_Command": "pay",
            "vnp_TmnCode": self.tmn_code,
            "vnp_Amount": str(to_vnpay_amount(amount)),
            "vnp_CurrCode": curr_code,
            "vnp_TxnRef": order_id,
            "vnp_OrderInfo": order_info,
            "vnp_OrderType": order_type,
            "vnp_Locale": locale,
            "vnp_ReturnUrl": return_url,
            "vnp_IpAddr": ip_addr,
            "vnp_CreateDate": create_date,
        }
        if expire_date:
            fields["vnp_ExpireDate"] = expire_date
        if bank_code:
            fields["vnp_BankCode"] = bank_code

        canonical = self._canonical_string(fields)
        secure_hash = self._hmac_hex(canonical)
        return f"{self.payment_url}?{canonical}&vnp_SecureHash={secure_hash}"

    def verify_callback_params(self, params: dict) -> None:
        """Verify a Return/IPN callback's vnp_SecureHash. Raises on failure.

        Pure signature check — no DB lookup, no idempotency, no success
        decision. Callers (Step 3) run this before trusting any other field.
        """
        received_hash = str(params.get("vnp_SecureHash") or "")
        if not received_hash:
            raise VnpaySignatureError("Callback VNPAY thiếu vnp_SecureHash.")
        expected_hash = self._sign(params)
        if not hmac.compare_digest(expected_hash, received_hash):
            raise VnpaySignatureError("Chữ ký callback VNPAY không hợp lệ.")

    @staticmethod
    def is_transaction_successful(params: dict) -> bool:
        """VNPAY-side transaction result only.

        Distinct from the RspCode our own IPN route replies to VNPAY with
        (Step 3) — that is a website-to-VNPAY acknowledgement, not this.
        """
        return (
            str(params.get("vnp_ResponseCode", "")) == "00"
            and str(params.get("vnp_TransactionStatus", "")) == "00"
        )

    @staticmethod
    def parse_callback_fields(params: dict) -> VnpayCallbackFields:
        """Normalize raw callback params into typed fields. No business logic."""
        amount_vnd: Decimal | None = None
        raw_amount = params.get("vnp_Amount")
        if raw_amount not in (None, ""):
            try:
                amount_vnd = Decimal(str(raw_amount)) / 100
            except InvalidOperation:
                amount_vnd = None
        return VnpayCallbackFields(
            is_success=VnpayClient.is_transaction_successful(params),
            response_code=_str_or_none(params.get("vnp_ResponseCode")),
            transaction_status=_str_or_none(params.get("vnp_TransactionStatus")),
            txn_ref=_str_or_none(params.get("vnp_TxnRef")),
            amount_vnd=amount_vnd,
            transaction_no=_str_or_none(params.get("vnp_TransactionNo")),
            bank_code=_str_or_none(params.get("vnp_BankCode")),
            pay_date=_str_or_none(params.get("vnp_PayDate")),
            order_info=_str_or_none(params.get("vnp_OrderInfo")),
        )

    def canonical_sign_string(self, fields: dict) -> str:
        """Expose the exact string that gets HMAC'd, for tests and Step 3 reuse."""
        return self._canonical_string(fields)

    def _sign(self, fields: dict) -> str:
        return self._hmac_hex(self._canonical_string(fields))

    def _canonical_string(self, fields: dict) -> str:
        """VNPAY PAY 2.1.0 canonicalization: sort keys, urlencode key AND
        value (PHP urlencode semantics — space becomes '+'), join pairs with
        '&' — NO trailing '&' after the last field. This canonical/hashdata
        string is distinct from the final URL query string, which does add
        '&vnp_SecureHash=...' after it (see build_payment_url).
        vnp_SecureHash/vnp_SecureHashType and any None/empty value are
        excluded before sorting.
        """
        filtered = {
            key: value
            for key, value in fields.items()
            if key not in _EXCLUDED_SIGN_FIELDS and value not in (None, "")
        }
        return "&".join(
            f"{quote_plus(str(key))}={quote_plus(str(filtered[key]))}"
            for key in sorted(filtered)
        )

    def _hmac_hex(self, data: str) -> str:
        return hmac.new(
            self._hash_secret.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha512,
        ).hexdigest()


def to_vnpay_amount(amount: Decimal | int | str) -> int:
    """Convert a whole-VND amount into vnp_Amount (VND x 100).

    Rejects anything that is not a positive, whole-VND value instead of
    silently rounding — a rounded amount here would desync from
    Payment.amount and could mask a real caller bug.
    """
    try:
        normalized = Decimal(str(amount))
    except (InvalidOperation, ValueError) as exc:
        raise VnpayAmountError("Số tiền VNPAY không hợp lệ.") from exc
    if normalized <= 0:
        raise VnpayAmountError("Số tiền VNPAY phải lớn hơn 0.")
    if normalized != normalized.to_integral_value():
        raise VnpayAmountError(
            "Số tiền VNPAY phải là số nguyên VND, không có phần thập phân."
        )
    return int(normalized) * 100


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None

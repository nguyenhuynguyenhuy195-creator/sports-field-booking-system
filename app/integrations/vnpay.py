from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

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

Transport = Callable[[str, dict, int], dict]

# Refund (vnp_Command=refund) uses a FIXED pipe-delimited field order for its
# checksum — NOT the sorted query-string canonicalization PAY/Return/IPN use.
# Request and response each have their own distinct order per VNPAY PAY 2.1.0.
_REFUND_REQUEST_HASH_FIELDS = (
    "vnp_RequestId",
    "vnp_Version",
    "vnp_Command",
    "vnp_TmnCode",
    "vnp_TransactionType",
    "vnp_TxnRef",
    "vnp_Amount",
    "vnp_TransactionNo",
    "vnp_TransactionDate",
    "vnp_CreateBy",
    "vnp_CreateDate",
    "vnp_IpAddr",
    "vnp_OrderInfo",
)
_REFUND_RESPONSE_HASH_FIELDS = (
    "vnp_ResponseId",
    "vnp_Command",
    "vnp_ResponseCode",
    "vnp_Message",
    "vnp_TmnCode",
    "vnp_TxnRef",
    "vnp_Amount",
    "vnp_BankCode",
    "vnp_PayDate",
    "vnp_TransactionNo",
    "vnp_TransactionType",
    "vnp_TransactionStatus",
    "vnp_OrderInfo",
)


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
        transport: Transport | None = None,
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
        self._transport = transport or self._post_json

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

    def refund(
        self,
        *,
        request_id: str,
        txn_ref: str,
        amount: Decimal | int | str,
        transaction_no: str,
        transaction_date: str,
        create_date: str,
        ip_addr: str,
        order_info: str,
        full_refund: bool,
        create_by: str = "system",
        version: str = "2.1.0",
    ) -> dict:
        """Submit a VNPAY refund (vnp_Command=refund) per PAY 2.1.0.

        txn_ref MUST be the ORIGINAL payment's vnp_TxnRef (Payment.order_id),
        never the Refund's own order_id — VNPAY identifies the transaction
        being refunded by its original reference, not ours for the refund.
        transaction_no should be the original Payment.provider_trans_id.
        transaction_date/create_date are caller-supplied, pre-formatted
        yyyyMMddHHmmss strings in Vietnam local time (GMT+7) — this client
        does no business-side date derivation, same as build_payment_url.

        Uses its OWN fixed pipe-delimited checksum (request and response
        each have a distinct field order) — this is NOT the sorted
        query-string canonicalization build_payment_url/verify_callback_params
        use for PAY/Return/IPN.

        Raises VnpayError/VnpaySignatureError before returning if the
        response signature, terminal code, txn_ref or amount do not match —
        callers must never apply a refund result that failed this check.
        """
        vnp_amount = to_vnpay_amount(amount)
        fields = {
            "vnp_RequestId": request_id,
            "vnp_Version": version,
            "vnp_Command": "refund",
            "vnp_TmnCode": self.tmn_code,
            "vnp_TransactionType": "02" if full_refund else "03",
            "vnp_TxnRef": txn_ref,
            "vnp_Amount": str(vnp_amount),
            "vnp_TransactionNo": transaction_no,
            "vnp_TransactionDate": transaction_date,
            "vnp_CreateBy": create_by,
            "vnp_CreateDate": create_date,
            "vnp_IpAddr": ip_addr,
            "vnp_OrderInfo": order_info,
        }
        fields["vnp_SecureHash"] = self._pipe_hash(
            fields, _REFUND_REQUEST_HASH_FIELDS
        )
        response = self._transport(self.api_url, fields, self.timeout_seconds)
        self._verify_refund_response(
            response,
            expected_txn_ref=txn_ref,
            expected_amount=vnp_amount,
        )
        return response

    def _verify_refund_response(
        self,
        response: dict,
        *,
        expected_txn_ref: str,
        expected_amount: int,
    ) -> None:
        received_hash = str(response.get("vnp_SecureHash") or "")
        if not received_hash:
            raise VnpaySignatureError(
                "Phản hồi hoàn tiền VNPAY thiếu vnp_SecureHash."
            )
        expected_hash = self._pipe_hash(response, _REFUND_RESPONSE_HASH_FIELDS)
        if not hmac.compare_digest(expected_hash, received_hash):
            raise VnpaySignatureError(
                "Chữ ký phản hồi hoàn tiền VNPAY không hợp lệ."
            )
        if str(response.get("vnp_TmnCode", "")) != self.tmn_code:
            raise VnpaySignatureError(
                "Mã terminal VNPAY trong phản hồi hoàn tiền không khớp."
            )
        if str(response.get("vnp_TxnRef", "")) != expected_txn_ref:
            raise VnpayError(
                "Mã giao dịch gốc trong phản hồi hoàn tiền VNPAY không khớp."
            )
        try:
            response_amount = int(Decimal(str(response.get("vnp_Amount", ""))))
        except (InvalidOperation, ValueError) as exc:
            raise VnpayError(
                "Số tiền trong phản hồi hoàn tiền VNPAY không hợp lệ."
            ) from exc
        if response_amount != expected_amount:
            raise VnpayError(
                "Số tiền trong phản hồi hoàn tiền VNPAY không khớp."
            )

    def _pipe_hash(self, fields: dict, order: tuple[str, ...]) -> str:
        raw = "|".join(str(fields.get(key) or "") for key in order)
        return self._hmac_hex(raw)

    def _post_json(self, url: str, payload: dict, timeout: int) -> dict:
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=UTF-8"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise VnpayError("Không thể kết nối VNPAY thử nghiệm lúc này.") from exc
        if not isinstance(result, dict):
            raise VnpayError("VNPAY thử nghiệm trả về thông tin không hợp lệ.")
        return result

    def verify_callback_params(self, params: dict) -> None:
        """Verify a Return/IPN callback's vnp_SecureHash. Raises on failure.

        Pure signature check — no DB lookup, no idempotency, no success
        decision. Callers (Step 3) run this before trusting any other field.

        Canonicalizes with drop_empty=False: a received callback must be
        hashed over exactly the vnp_* fields VNPAY actually sent (minus
        vnp_SecureHash/vnp_SecureHashType), including any field VNPAY chose
        to send with an empty string value — VNPAY signed whatever it sent,
        so dropping an empty field here would silently recompute a different
        hash and reject a legitimately-signed callback.
        """
        received_hash = str(params.get("vnp_SecureHash") or "")
        if not received_hash:
            raise VnpaySignatureError("Callback VNPAY thiếu vnp_SecureHash.")
        expected_hash = self._sign(params, drop_empty=False)
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

    def canonical_sign_string(self, fields: dict, *, drop_empty: bool = True) -> str:
        """Expose the exact string that gets HMAC'd, for tests and Step 3 reuse.

        drop_empty=True (default): request/outbound style — a field with an
        empty value is treated as "not sent" (matches build_payment_url,
        where optional fields are simply omitted by the caller already; this
        is a defensive net for the same effect).
        drop_empty=False: callback/inbound style — canonicalize exactly the
        fields received, empty-string values included (see
        verify_callback_params for why this must not drop them).
        """
        return self._canonical_string(fields, drop_empty=drop_empty)

    def _sign(self, fields: dict, *, drop_empty: bool = True) -> str:
        return self._hmac_hex(self._canonical_string(fields, drop_empty=drop_empty))

    def _canonical_string(self, fields: dict, *, drop_empty: bool = True) -> str:
        """VNPAY PAY 2.1.0 canonicalization: sort keys, urlencode key AND
        value (PHP urlencode semantics — space becomes '+'), join pairs with
        '&' — NO trailing '&' after the last field. This canonical/hashdata
        string is distinct from the final URL query string, which does add
        '&vnp_SecureHash=...' after it (see build_payment_url).

        vnp_SecureHash/vnp_SecureHashType and any None value are always
        excluded before sorting. An empty string value is additionally
        excluded only when drop_empty=True — see canonical_sign_string.
        """
        filtered = {
            key: value
            for key, value in fields.items()
            if key not in _EXCLUDED_SIGN_FIELDS
            and value is not None
            and (value != "" or not drop_empty)
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

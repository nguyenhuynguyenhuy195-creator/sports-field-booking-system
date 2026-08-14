from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app


class MomoAPIError(RuntimeError):
    """Raised when MoMo cannot accept or return a usable API response."""


class MomoConfigurationError(MomoAPIError):
    """Raised when Sandbox credentials or callback URLs are incomplete."""


class MomoSignatureError(MomoAPIError):
    """Raised when a response or notification signature is invalid."""


Transport = Callable[[str, dict, int], dict]


class MomoClient:
    CREATE_PATH = "/v2/gateway/api/create"
    QUERY_PATH = "/v2/gateway/api/query"
    REFUND_PATH = "/v2/gateway/api/refund"
    REFUND_QUERY_PATH = "/v2/gateway/api/refund/query"

    def __init__(
        self,
        *,
        partner_code: str,
        access_key: str,
        secret_key: str,
        base_url: str = "https://test-payment.momo.vn",
        timeout_seconds: int = 30,
        transport: Transport | None = None,
    ) -> None:
        if not partner_code or not access_key or not secret_key:
            raise MomoConfigurationError("Thiếu thông tin xác thực MoMo Sandbox.")
        self.partner_code = partner_code
        self.access_key = access_key
        self._secret_key = secret_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = max(int(timeout_seconds), 30)
        self._transport = transport or self._post_json

    @classmethod
    def from_app_config(cls) -> "MomoClient":
        if not current_app.config.get("MOMO_ENABLED"):
            raise MomoConfigurationError("MoMo Sandbox chưa được bật trong cấu hình.")
        return cls(
            partner_code=current_app.config.get("MOMO_PARTNER_CODE", ""),
            access_key=current_app.config.get("MOMO_ACCESS_KEY", ""),
            secret_key=current_app.config.get("MOMO_SECRET_KEY", ""),
            base_url=current_app.config.get(
                "MOMO_BASE_URL", "https://test-payment.momo.vn"
            ),
            timeout_seconds=current_app.config.get("MOMO_TIMEOUT_SECONDS", 30),
        )

    def create_payment(
        self,
        *,
        order_id: str,
        request_id: str,
        amount: Decimal,
        order_info: str,
        redirect_url: str,
        ipn_url: str,
    ) -> dict:
        amount_value = _whole_vnd(amount)
        signed = {
            "accessKey": self.access_key,
            "amount": amount_value,
            "extraData": "",
            "ipnUrl": ipn_url,
            "orderId": order_id,
            "orderInfo": order_info,
            "partnerCode": self.partner_code,
            "redirectUrl": redirect_url,
            "requestId": request_id,
            "requestType": "captureWallet",
        }
        payload = {
            key: value for key, value in signed.items() if key != "accessKey"
        }
        payload.update(
            {
                "lang": "vi",
                "signature": self._sign(signed),
            }
        )
        response = self._transport(self.CREATE_PATH, payload, self.timeout_seconds)
        self._verify_create_response(response)
        return response

    def query_payment(self, *, order_id: str, request_id: str) -> dict:
        signed = {
            "accessKey": self.access_key,
            "orderId": order_id,
            "partnerCode": self.partner_code,
            "requestId": request_id,
        }
        payload = {
            "partnerCode": self.partner_code,
            "requestId": request_id,
            "orderId": order_id,
            "lang": "vi",
            "signature": self._sign(signed),
        }
        return self._transport(self.QUERY_PATH, payload, self.timeout_seconds)

    def refund_payment(
        self,
        *,
        order_id: str,
        request_id: str,
        amount: Decimal,
        trans_id: str,
        description: str,
    ) -> dict:
        amount_value = _whole_vnd(amount)
        signed = {
            "accessKey": self.access_key,
            "amount": amount_value,
            "description": description,
            "orderId": order_id,
            "partnerCode": self.partner_code,
            "requestId": request_id,
            "transId": trans_id,
        }
        payload = {
            key: value for key, value in signed.items() if key != "accessKey"
        }
        payload.update({"lang": "vi", "signature": self._sign(signed)})
        return self._transport(self.REFUND_PATH, payload, self.timeout_seconds)

    def query_refund(self, *, order_id: str, request_id: str) -> dict:
        signed = {
            "accessKey": self.access_key,
            "orderId": order_id,
            "partnerCode": self.partner_code,
            "requestId": request_id,
        }
        payload = {
            "partnerCode": self.partner_code,
            "requestId": request_id,
            "orderId": order_id,
            "lang": "vi",
            "signature": self._sign(signed),
        }
        return self._transport(
            self.REFUND_QUERY_PATH,
            payload,
            self.timeout_seconds,
        )

    def verify_payment_notification(self, payload: dict) -> None:
        if str(payload.get("partnerCode", "")) != self.partner_code:
            raise MomoSignatureError("Mã đối tác trong callback MoMo không khớp.")
        signed = {
            "accessKey": self.access_key,
            "amount": payload.get("amount", ""),
            "extraData": payload.get("extraData", ""),
            "message": payload.get("message", ""),
            "orderId": payload.get("orderId", ""),
            "orderInfo": payload.get("orderInfo", ""),
            "orderType": payload.get("orderType", ""),
            "partnerCode": payload.get("partnerCode", ""),
            "payType": payload.get("payType", ""),
            "requestId": payload.get("requestId", ""),
            "responseTime": payload.get("responseTime", ""),
            "resultCode": payload.get("resultCode", ""),
            "transId": payload.get("transId", ""),
        }
        self._verify_signature(signed, str(payload.get("signature", "")))

    def _verify_create_response(self, payload: dict) -> None:
        signed = {
            "accessKey": self.access_key,
            "amount": payload.get("amount", ""),
            "message": payload.get("message", ""),
            "orderId": payload.get("orderId", ""),
            "partnerCode": payload.get("partnerCode", ""),
            "payUrl": payload.get("payUrl", ""),
            "requestId": payload.get("requestId", ""),
            "responseTime": payload.get("responseTime", ""),
            "resultCode": payload.get("resultCode", ""),
        }
        self._verify_signature(signed, str(payload.get("signature", "")))

    def _sign(self, fields: dict) -> str:
        raw = "&".join(f"{key}={value}" for key, value in fields.items())
        return hmac.new(
            self._secret_key.encode("utf-8"),
            raw.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _verify_signature(self, fields: dict, received: str) -> None:
        if not received or not hmac.compare_digest(self._sign(fields), received):
            raise MomoSignatureError("Chữ ký phản hồi MoMo không hợp lệ.")

    def _post_json(self, path: str, payload: dict, timeout: int) -> dict:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=UTF-8"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise MomoAPIError("Không thể kết nối MoMo Sandbox lúc này.") from exc
        if not isinstance(result, dict):
            raise MomoAPIError("MoMo Sandbox trả về dữ liệu không hợp lệ.")
        return result


def _whole_vnd(amount: Decimal) -> int:
    normalized = Decimal(amount)
    if normalized <= 0 or normalized != normalized.to_integral_value():
        raise MomoAPIError("Số tiền MoMo phải là số nguyên dương theo VND.")
    value = int(normalized)
    if value < 1000 or value > 50_000_000:
        raise MomoAPIError("Số tiền MoMo phải từ 1.000đ đến 50.000.000đ.")
    return value

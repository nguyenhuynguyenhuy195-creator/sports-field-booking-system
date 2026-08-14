import hashlib
import hmac
from decimal import Decimal

import pytest

from app.integrations import MomoClient, MomoSignatureError


SECRET = "sandbox-secret"


def sign(fields: dict) -> str:
    raw = "&".join(f"{key}={value}" for key, value in fields.items())
    return hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()


def test_create_payment_uses_documented_hmac_and_verifies_response():
    def transport(path, payload, timeout):
        assert path == "/v2/gateway/api/create"
        assert timeout == 30
        request_fields = {
            "accessKey": "sandbox-access",
            "amount": 120000,
            "extraData": "",
            "ipnUrl": "https://example.test/payments/momo/ipn",
            "orderId": "MOMO-PAY-1-ABC",
            "orderInfo": "Cọc booking BK1",
            "partnerCode": "sandbox-partner",
            "redirectUrl": "https://example.test/payments/momo/return",
            "requestId": "request-1",
            "requestType": "captureWallet",
        }
        assert payload["signature"] == sign(request_fields)
        response = {
            "partnerCode": "sandbox-partner",
            "orderId": payload["orderId"],
            "requestId": payload["requestId"],
            "amount": payload["amount"],
            "responseTime": 123456789,
            "message": "Successful.",
            "resultCode": 0,
            "payUrl": "https://test-payment.momo.vn/pay/test",
        }
        response["signature"] = sign(
            {
                "accessKey": "sandbox-access",
                "amount": response["amount"],
                "message": response["message"],
                "orderId": response["orderId"],
                "partnerCode": response["partnerCode"],
                "payUrl": response["payUrl"],
                "requestId": response["requestId"],
                "responseTime": response["responseTime"],
                "resultCode": response["resultCode"],
            }
        )
        return response

    client = MomoClient(
        partner_code="sandbox-partner",
        access_key="sandbox-access",
        secret_key=SECRET,
        transport=transport,
    )
    response = client.create_payment(
        order_id="MOMO-PAY-1-ABC",
        request_id="request-1",
        amount=Decimal("120000"),
        order_info="Cọc booking BK1",
        redirect_url="https://example.test/payments/momo/return",
        ipn_url="https://example.test/payments/momo/ipn",
    )

    assert response["resultCode"] == 0


def test_payment_notification_rejects_tampered_amount():
    client = MomoClient(
        partner_code="sandbox-partner",
        access_key="sandbox-access",
        secret_key=SECRET,
        transport=lambda *_: {},
    )
    payload = {
        "amount": 120000,
        "extraData": "",
        "message": "Successful.",
        "orderId": "MOMO-PAY-1-ABC",
        "orderInfo": "Cọc booking BK1",
        "orderType": "momo_wallet",
        "partnerCode": "sandbox-partner",
        "payType": "qr",
        "requestId": "request-1",
        "responseTime": 123456789,
        "resultCode": 0,
        "transId": 998877,
    }
    payload["signature"] = sign(
        {"accessKey": "sandbox-access", **payload}
    )
    client.verify_payment_notification(payload)

    payload["amount"] = 120001
    with pytest.raises(MomoSignatureError):
        client.verify_payment_notification(payload)


def test_refund_request_uses_documented_signature_order():
    def transport(path, payload, timeout):
        assert path == "/v2/gateway/api/refund"
        assert payload["signature"] == sign(
            {
                "accessKey": "sandbox-access",
                "amount": 48000,
                "description": "Hoàn cọc",
                "orderId": "MOMO-REFUND-1",
                "partnerCode": "sandbox-partner",
                "requestId": "refund-request-1",
                "transId": "998877",
            }
        )
        return {
            "resultCode": 0,
            "transId": 112233,
            "orderId": payload["orderId"],
        }

    client = MomoClient(
        partner_code="sandbox-partner",
        access_key="sandbox-access",
        secret_key=SECRET,
        transport=transport,
    )
    response = client.refund_payment(
        order_id="MOMO-REFUND-1",
        request_id="refund-request-1",
        amount=Decimal("48000"),
        trans_id="998877",
        description="Hoàn cọc",
    )

    assert response["transId"] == 112233

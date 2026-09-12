import json
from decimal import Decimal
from urllib.parse import parse_qsl, urlsplit

import pytest

from app.integrations import (
    VnpayAmountError,
    VnpayClient,
    VnpayConfigurationError,
    VnpayError,
    VnpaySignatureError,
    to_vnpay_amount,
)


TMN_CODE = "TESTCODE01"
HASH_SECRET = "SECRETKEY123"
PAYMENT_URL = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
API_URL = "https://sandbox.vnpayment.vn/merchant_webapi/api/transaction"

# Fixed test vector, computed independently offline with a standalone
# hmac.new(...) call over a manually sorted/encoded canonical string — NOT
# derived by calling VnpayClient. If either the canonical-string builder or
# the HMAC call in the implementation has a bug, this literal will not match
# even though "sign now, verify same" would still pass.
FIXED_FIELDS = {
    "vnp_Version": "2.1.0",
    "vnp_Command": "pay",
    "vnp_TmnCode": TMN_CODE,
    "vnp_Amount": "10000000",
    "vnp_CurrCode": "VND",
    "vnp_TxnRef": "ORDER123",
    "vnp_OrderInfo": "Thanh toan don hang",
    "vnp_OrderType": "other",
    "vnp_Locale": "vn",
    "vnp_ReturnUrl": "https://example.com/return",
    "vnp_IpAddr": "127.0.0.1",
    "vnp_CreateDate": "20260912103000",
}
FIXED_CANONICAL = (
    "vnp_Amount=10000000&"
    "vnp_Command=pay&"
    "vnp_CreateDate=20260912103000&"
    "vnp_CurrCode=VND&"
    "vnp_IpAddr=127.0.0.1&"
    "vnp_Locale=vn&"
    "vnp_OrderInfo=Thanh+toan+don+hang&"
    "vnp_OrderType=other&"
    "vnp_ReturnUrl=https%3A%2F%2Fexample.com%2Freturn&"
    "vnp_TmnCode=TESTCODE01&"
    "vnp_TxnRef=ORDER123&"
    "vnp_Version=2.1.0"
)
FIXED_DIGEST = (
    "89139e26a23b86c5c5750e9605c66a1cde5255d5933ac1563a8ceb36a540d2f"
    "eadb85c4a1be60c2b9f4d0db5c56d7033cf0d17f34a64658890a6b3112e1716b3"
)


def make_client(**overrides) -> VnpayClient:
    kwargs = dict(
        tmn_code=TMN_CODE,
        hash_secret=HASH_SECRET,
        payment_url=PAYMENT_URL,
        api_url=API_URL,
    )
    kwargs.update(overrides)
    return VnpayClient(**kwargs)


def query_dict(url: str) -> dict:
    return dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))


# --- 1. Construction / config -------------------------------------------------


def test_client_construction_requires_credentials_and_does_not_expose_secret():
    with pytest.raises(VnpayConfigurationError):
        VnpayClient(
            tmn_code="",
            hash_secret=HASH_SECRET,
            payment_url=PAYMENT_URL,
            api_url=API_URL,
        )

    client = make_client()
    assert HASH_SECRET not in repr(client)
    assert HASH_SECRET not in str(client.__dict__.get("tmn_code", ""))
    # Only the private, name-mangled attribute holds the secret.
    assert client._hash_secret == HASH_SECRET
    assert "_hash_secret" not in repr(client)


def test_from_app_config_requires_vnpay_enabled(app):
    with app.app_context():
        app.config["VNPAY_ENABLED"] = False
        with pytest.raises(VnpayConfigurationError):
            VnpayClient.from_app_config()

        app.config.update(
            VNPAY_ENABLED=True,
            VNPAY_TMN_CODE=TMN_CODE,
            VNPAY_HASH_SECRET=HASH_SECRET,
            VNPAY_PAYMENT_URL=PAYMENT_URL,
            VNPAY_API_URL=API_URL,
            VNPAY_TIMEOUT_SECONDS=30,
        )
        client = VnpayClient.from_app_config()
        assert client.tmn_code == TMN_CODE


# --- 2. Amount helper ----------------------------------------------------------


def test_amount_is_multiplied_by_100():
    assert to_vnpay_amount(120000) == 12000000
    assert to_vnpay_amount(Decimal("120000")) == 12000000
    assert to_vnpay_amount("120000") == 12000000


@pytest.mark.parametrize("bad_amount", [0, -5000, "-1", "abc"])
def test_amount_rejects_non_positive_or_invalid_values(bad_amount):
    with pytest.raises(VnpayAmountError):
        to_vnpay_amount(bad_amount)


def test_amount_rejects_fractional_vnd_instead_of_silently_rounding():
    with pytest.raises(VnpayAmountError):
        to_vnpay_amount(Decimal("120000.50"))


# --- 3. Canonicalization / signing ---------------------------------------------


def test_canonical_string_sorts_keys_alphabetically():
    client = make_client()
    canonical = client.canonical_sign_string(
        {
            "vnp_TxnRef": "ORDER1",
            "vnp_Amount": "1000",
            "vnp_Command": "pay",
        }
    )
    assert canonical == "vnp_Amount=1000&vnp_Command=pay&vnp_TxnRef=ORDER1"
    assert not canonical.endswith("&")


def test_canonical_string_url_encodes_special_characters_and_spaces():
    client = make_client()
    canonical = client.canonical_sign_string(
        {
            "vnp_OrderInfo": "Thanh toan don hang",
            "vnp_ReturnUrl": "https://example.com/return",
        }
    )
    assert "Thanh+toan+don+hang" in canonical
    assert " " not in canonical
    assert "https%3A%2F%2Fexample.com%2Freturn" in canonical


def test_canonical_string_excludes_secure_hash_fields_and_empty_values():
    client = make_client()
    canonical = client.canonical_sign_string(
        {
            "vnp_TxnRef": "ORDER1",
            "vnp_SecureHash": "should-not-appear",
            "vnp_SecureHashType": "SHA512",
            "vnp_BankCode": "",
            "vnp_ExpireDate": None,
        }
    )
    assert canonical == "vnp_TxnRef=ORDER1"
    assert "SecureHash" not in canonical
    assert "BankCode" not in canonical
    assert "ExpireDate" not in canonical


def test_canonical_string_has_no_trailing_ampersand():
    client = make_client()
    canonical = client.canonical_sign_string(FIXED_FIELDS)
    assert not canonical.endswith("&")


def test_fixed_vector_canonical_string_matches_independently_built_string():
    client = make_client()
    assert client.canonical_sign_string(FIXED_FIELDS) == FIXED_CANONICAL
    assert not FIXED_CANONICAL.endswith("&")


def test_fixed_vector_hmac_sha512_matches_independently_computed_digest():
    client = make_client()
    signed_url = client.build_payment_url(
        order_id=FIXED_FIELDS["vnp_TxnRef"],
        amount=Decimal(FIXED_FIELDS["vnp_Amount"]) / 100,
        order_info=FIXED_FIELDS["vnp_OrderInfo"],
        return_url=FIXED_FIELDS["vnp_ReturnUrl"],
        ip_addr=FIXED_FIELDS["vnp_IpAddr"],
        create_date=FIXED_FIELDS["vnp_CreateDate"],
        version=FIXED_FIELDS["vnp_Version"],
    )
    params = query_dict(signed_url)
    assert params["vnp_SecureHash"] == FIXED_DIGEST


# --- 4. build_payment_url -------------------------------------------------------


def test_build_payment_url_contains_documented_fields():
    client = make_client()
    url = client.build_payment_url(
        order_id="ORDER123",
        amount=120000,
        order_info="Cọc booking",
        return_url="https://example.test/return",
        ip_addr="203.0.113.5",
        create_date="20260912103000",
    )
    assert url.startswith(PAYMENT_URL + "?")
    params = query_dict(url)
    assert params["vnp_Version"] == "2.1.0"
    assert params["vnp_Command"] == "pay"
    assert params["vnp_TmnCode"] == TMN_CODE
    assert params["vnp_Amount"] == "12000000"
    assert params["vnp_CurrCode"] == "VND"
    assert params["vnp_TxnRef"] == "ORDER123"
    assert params["vnp_Locale"] == "vn"
    assert params["vnp_IpAddr"] == "203.0.113.5"
    assert params["vnp_CreateDate"] == "20260912103000"
    assert "vnp_SecureHash" in params
    assert "vnp_BankCode" not in params


def test_build_payment_url_with_bank_code_vnpayqr_adds_bank_code_param():
    client = make_client()
    url = client.build_payment_url(
        order_id="ORDER123",
        amount=120000,
        order_info="Cọc booking",
        return_url="https://example.test/return",
        ip_addr="203.0.113.5",
        create_date="20260912103000",
        bank_code="VNPAYQR",
    )
    params = query_dict(url)
    assert params["vnp_BankCode"] == "VNPAYQR"


def test_build_payment_url_joins_secure_hash_with_a_single_ampersand():
    client = make_client()
    url = client.build_payment_url(
        order_id="ORDER123",
        amount=120000,
        order_info="Coc booking",
        return_url="https://example.test/return",
        ip_addr="203.0.113.5",
        create_date="20260912103000",
    )
    query = urlsplit(url).query
    # Canonical string has no trailing "&"; the URL query must still glue it
    # to vnp_SecureHash with exactly one "&" — no "&&" and no missing "&".
    assert "&&" not in query
    assert query.endswith("&vnp_SecureHash=" + query_dict(url)["vnp_SecureHash"])
    assert "?" not in query  # sanity: query is only the part after "?"


def test_build_payment_url_without_bank_code_omits_bank_code_param():
    client = make_client()
    url = client.build_payment_url(
        order_id="ORDER123",
        amount=120000,
        order_info="Cọc booking",
        return_url="https://example.test/return",
        ip_addr="203.0.113.5",
        create_date="20260912103000",
        bank_code=None,
    )
    params = query_dict(url)
    assert "vnp_BankCode" not in params


# --- 5. Callback verification ---------------------------------------------------


def _signed_callback(client: VnpayClient, **fields) -> dict:
    payload = {
        "vnp_TxnRef": "ORDER123",
        "vnp_Amount": "12000000",
        "vnp_ResponseCode": "00",
        "vnp_TransactionStatus": "00",
        "vnp_TransactionNo": "998877",
        "vnp_BankCode": "NCB",
        "vnp_PayDate": "20260912103500",
        "vnp_OrderInfo": "Coc booking",
        **fields,
    }
    payload["vnp_SecureHash"] = client._sign(payload)
    return payload


def test_verify_callback_params_accepts_correctly_signed_payload():
    client = make_client()
    payload = _signed_callback(client)
    client.verify_callback_params(payload)  # must not raise


def test_verify_callback_params_rejects_tampered_field():
    client = make_client()
    payload = _signed_callback(client)
    payload["vnp_Amount"] = "12000001"
    with pytest.raises(VnpaySignatureError):
        client.verify_callback_params(payload)


def test_verify_callback_params_rejects_missing_secure_hash():
    client = make_client()
    payload = _signed_callback(client)
    del payload["vnp_SecureHash"]
    with pytest.raises(VnpaySignatureError):
        client.verify_callback_params(payload)


def test_verify_callback_params_ignores_secure_hash_type_in_signature():
    client = make_client()
    payload = _signed_callback(client)
    # Adding vnp_SecureHashType after signing must not affect verification —
    # it is excluded from the canonical payload on both sides.
    payload["vnp_SecureHashType"] = "SHA512"
    client.verify_callback_params(payload)  # must not raise


# Fixed vector for a callback where VNPAY sent vnp_BankCode with an EMPTY
# value — computed independently offline (standalone hmac.new call over a
# manually sorted/encoded string), not derived by calling VnpayClient.
FIXED_EMPTY_FIELD_CALLBACK = {
    "vnp_TxnRef": "ORDER123",
    "vnp_Amount": "12000000",
    "vnp_ResponseCode": "00",
    "vnp_TransactionStatus": "00",
    "vnp_TransactionNo": "998877",
    "vnp_BankCode": "",
    "vnp_PayDate": "20260912103500",
}
FIXED_EMPTY_FIELD_CANONICAL = (
    "vnp_Amount=12000000&vnp_BankCode=&vnp_PayDate=20260912103500&"
    "vnp_ResponseCode=00&vnp_TransactionNo=998877&vnp_TransactionStatus=00&"
    "vnp_TxnRef=ORDER123"
)
FIXED_EMPTY_FIELD_DIGEST = (
    "18b8ac08b8819247884a61d3f228cb2e2ac8e5f35125254866f3003bb0fcfce"
    "353b279e7396c394567a52c3bc3d3e6e416916d61045e321980af499b92c081ab"
)


def test_callback_canonical_keeps_signed_empty_value_field():
    client = make_client()
    canonical = client.canonical_sign_string(
        FIXED_EMPTY_FIELD_CALLBACK, drop_empty=False
    )
    assert canonical == FIXED_EMPTY_FIELD_CANONICAL
    assert "vnp_BankCode=&" in canonical or canonical.endswith("vnp_BankCode=")


def test_verify_callback_params_accepts_signed_empty_value_field():
    client = make_client()
    payload = dict(FIXED_EMPTY_FIELD_CALLBACK)
    payload["vnp_SecureHash"] = FIXED_EMPTY_FIELD_DIGEST
    client.verify_callback_params(payload)  # must not raise


def test_dropping_empty_field_would_have_produced_a_different_hash():
    """Proves drop_empty actually changes the result — not a no-op flag.

    If verify_callback_params ever regresses to dropping empty values again,
    this fixed digest would stop matching and the test above would fail.
    """
    client = make_client()
    dropped_hash = client._sign(FIXED_EMPTY_FIELD_CALLBACK, drop_empty=True)
    assert dropped_hash != FIXED_EMPTY_FIELD_DIGEST


# --- 6. Success semantics --------------------------------------------------------


def test_is_transaction_successful_requires_both_codes_to_be_00():
    assert VnpayClient.is_transaction_successful(
        {"vnp_ResponseCode": "00", "vnp_TransactionStatus": "00"}
    )


def test_is_transaction_successful_false_when_response_code_ok_but_status_not():
    assert not VnpayClient.is_transaction_successful(
        {"vnp_ResponseCode": "00", "vnp_TransactionStatus": "01"}
    )


def test_is_transaction_successful_false_when_status_ok_but_response_code_not():
    assert not VnpayClient.is_transaction_successful(
        {"vnp_ResponseCode": "24", "vnp_TransactionStatus": "00"}
    )


def test_parse_callback_fields_normalizes_amount_back_to_vnd():
    parsed = VnpayClient.parse_callback_fields(
        {
            "vnp_ResponseCode": "00",
            "vnp_TransactionStatus": "00",
            "vnp_Amount": "12000000",
            "vnp_TxnRef": "ORDER123",
        }
    )
    assert parsed.is_success is True
    assert parsed.amount_vnd == Decimal("120000")
    assert parsed.txn_ref == "ORDER123"


# --- Step 6: Refund (vnp_Command=refund) -----------------------------------------
#
# The refund request AND response each use their OWN fixed pipe-delimited
# checksum order per VNPAY PAY 2.1.0 — NOT the sorted query-string
# canonicalization build_payment_url/verify_callback_params use. Fixed
# vectors below are computed independently offline with a standalone
# hmac.new(...) call over a manually pipe-joined string — not derived by
# calling VnpayClient — for the same reason as FIXED_DIGEST above.

REFUND_REQUEST_ID = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
REFUND_TXN_REF = "VNPAYPAY1ABCDEF0123456789"
REFUND_ORDER_INFO = f"Hoan tien giao dich {REFUND_TXN_REF}"

FIXED_REFUND_REQUEST_DIGEST = (
    "ccd115aedec73f0251b726341ee92158588bb81c50c2474365c552706a44819"
    "d2e3b333923dc71a36023775512c1d7c288dc06a09351335b76837ac2a1d85410"
)
FIXED_REFUND_RESPONSE_DIGEST = (
    "a506cacf83bc03e4a538bd4a9b5294b58beaa69ba3b83158858870d4c5a163d1"
    "308ef5e66dddb52ffd4f162306c09ff7c1c3075f0f4b45e20cc61c6986b15934"
)


def _signed_refund_response(
    *,
    response_code: str = "00",
    transaction_status: str = "00",
    amount: str = "6000000",
    txn_ref: str = REFUND_TXN_REF,
    digest: str | None = None,
) -> dict:
    response = {
        "vnp_ResponseId": "resp-req-001",
        "vnp_Command": "refund",
        "vnp_ResponseCode": response_code,
        "vnp_Message": "Confirm Success",
        "vnp_TmnCode": TMN_CODE,
        "vnp_TxnRef": txn_ref,
        "vnp_Amount": amount,
        "vnp_BankCode": "NCB",
        "vnp_PayDate": "20260912103500",
        "vnp_TransactionNo": "998877",
        "vnp_TransactionType": "02",
        "vnp_TransactionStatus": transaction_status,
        "vnp_OrderInfo": REFUND_ORDER_INFO,
    }
    client = make_client()
    response["vnp_SecureHash"] = digest or client._pipe_hash(
        response,
        (
            "vnp_ResponseId", "vnp_Command", "vnp_ResponseCode", "vnp_Message",
            "vnp_TmnCode", "vnp_TxnRef", "vnp_Amount", "vnp_BankCode",
            "vnp_PayDate", "vnp_TransactionNo", "vnp_TransactionType",
            "vnp_TransactionStatus", "vnp_OrderInfo",
        ),
    )
    return response


def test_refund_request_checksum_matches_fixed_vector_field_order():
    """Proves the request hash is built over EXACTLY the 13 documented
    fields in EXACTLY the documented order — any reordering or omission
    would produce a digest that no longer matches this independently
    computed literal."""
    captured = {}

    def transport(url, payload, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout"] = timeout
        return _signed_refund_response()

    client = make_client(transport=transport)
    client.refund(
        request_id=REFUND_REQUEST_ID,
        txn_ref=REFUND_TXN_REF,
        amount=60000,
        transaction_no="998877",
        transaction_date="20260912103000",
        create_date="20260913090000",
        ip_addr="127.0.0.1",
        order_info=REFUND_ORDER_INFO,
        full_refund=True,
    )

    assert captured["url"] == API_URL
    assert captured["timeout"] == client.timeout_seconds
    assert captured["payload"]["vnp_SecureHash"] == FIXED_REFUND_REQUEST_DIGEST


def test_refund_amount_is_vnd_times_100():
    captured = {}

    def transport(url, payload, timeout):
        captured["payload"] = payload
        return _signed_refund_response()

    client = make_client(transport=transport)
    client.refund(
        request_id=REFUND_REQUEST_ID,
        txn_ref=REFUND_TXN_REF,
        amount=60000,
        transaction_no="998877",
        transaction_date="20260912103000",
        create_date="20260913090000",
        ip_addr="127.0.0.1",
        order_info=REFUND_ORDER_INFO,
        full_refund=True,
    )
    assert captured["payload"]["vnp_Amount"] == "6000000"


def test_refund_full_uses_transaction_type_02():
    captured = {}

    def transport(url, payload, timeout):
        captured["payload"] = payload
        return _signed_refund_response()

    client = make_client(transport=transport)
    client.refund(
        request_id=REFUND_REQUEST_ID, txn_ref=REFUND_TXN_REF, amount=60000,
        transaction_no="998877", transaction_date="20260912103000",
        create_date="20260913090000", ip_addr="127.0.0.1",
        order_info=REFUND_ORDER_INFO, full_refund=True,
    )
    assert captured["payload"]["vnp_TransactionType"] == "02"


def test_refund_partial_uses_transaction_type_03():
    captured = {}

    def transport(url, payload, timeout):
        captured["payload"] = payload
        return _signed_refund_response()

    client = make_client(transport=transport)
    client.refund(
        request_id=REFUND_REQUEST_ID, txn_ref=REFUND_TXN_REF, amount=60000,
        transaction_no="998877", transaction_date="20260912103000",
        create_date="20260913090000", ip_addr="127.0.0.1",
        order_info=REFUND_ORDER_INFO, full_refund=False,
    )
    assert captured["payload"]["vnp_TransactionType"] == "03"


def test_refund_uses_the_original_payment_txn_ref_it_was_given():
    captured = {}

    def transport(url, payload, timeout):
        captured["payload"] = payload
        return _signed_refund_response()

    client = make_client(transport=transport)
    client.refund(
        request_id=REFUND_REQUEST_ID, txn_ref=REFUND_TXN_REF, amount=60000,
        transaction_no="998877", transaction_date="20260912103000",
        create_date="20260913090000", ip_addr="127.0.0.1",
        order_info=REFUND_ORDER_INFO, full_refund=True,
    )
    # The client never invents its own reference — it is exactly the
    # caller-supplied original Payment.order_id, not a Refund-generated id.
    assert captured["payload"]["vnp_TxnRef"] == REFUND_TXN_REF


def test_refund_rejects_response_with_invalid_signature():
    def transport(url, payload, timeout):
        response = _signed_refund_response()
        response["vnp_SecureHash"] = "0" * 128  # syntactically valid, wrong
        return response

    client = make_client(transport=transport)
    with pytest.raises(VnpaySignatureError):
        client.refund(
            request_id=REFUND_REQUEST_ID, txn_ref=REFUND_TXN_REF, amount=60000,
            transaction_no="998877", transaction_date="20260912103000",
            create_date="20260913090000", ip_addr="127.0.0.1",
            order_info=REFUND_ORDER_INFO, full_refund=True,
        )


def test_refund_rejects_response_with_mismatched_amount():
    def transport(url, payload, timeout):
        # Validly signed for a DIFFERENT amount than what was requested.
        return _signed_refund_response(amount="9999900")

    client = make_client(transport=transport)
    with pytest.raises(VnpayError):
        client.refund(
            request_id=REFUND_REQUEST_ID, txn_ref=REFUND_TXN_REF, amount=60000,
            transaction_no="998877", transaction_date="20260912103000",
            create_date="20260913090000", ip_addr="127.0.0.1",
            order_info=REFUND_ORDER_INFO, full_refund=True,
        )


def test_refund_rejects_response_with_mismatched_txn_ref():
    def transport(url, payload, timeout):
        # Validly signed for a DIFFERENT vnp_TxnRef than what was requested.
        return _signed_refund_response(txn_ref="SOME-OTHER-ORDER")

    client = make_client(transport=transport)
    with pytest.raises(VnpayError):
        client.refund(
            request_id=REFUND_REQUEST_ID, txn_ref=REFUND_TXN_REF, amount=60000,
            transaction_no="998877", transaction_date="20260912103000",
            create_date="20260913090000", ip_addr="127.0.0.1",
            order_info=REFUND_ORDER_INFO, full_refund=True,
        )


def test_refund_network_error_raises_clean_vnpay_error(monkeypatch):
    import app.integrations.vnpay as vnpay_module
    from urllib.error import URLError

    def broken_urlopen(*args, **kwargs):
        # Real urlopen wraps a socket failure as URLError, not a bare OSError.
        raise URLError(OSError("connection refused"))

    monkeypatch.setattr(vnpay_module, "urlopen", broken_urlopen)
    client = make_client()  # default transport = real _post_json
    with pytest.raises(VnpayError):
        client.refund(
            request_id=REFUND_REQUEST_ID, txn_ref=REFUND_TXN_REF, amount=60000,
            transaction_no="998877", transaction_date="20260912103000",
            create_date="20260913090000", ip_addr="127.0.0.1",
            order_info=REFUND_ORDER_INFO, full_refund=True,
        )


def test_refund_invalid_json_response_raises_clean_vnpay_error(monkeypatch):
    import app.integrations.vnpay as vnpay_module

    class FakeHttpResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def read(self):
            return b"not json at all"

    def fake_urlopen(*args, **kwargs):
        return FakeHttpResponse()

    monkeypatch.setattr(vnpay_module, "urlopen", fake_urlopen)
    client = make_client()  # default transport = real _post_json
    with pytest.raises(VnpayError):
        client.refund(
            request_id=REFUND_REQUEST_ID, txn_ref=REFUND_TXN_REF, amount=60000,
            transaction_no="998877", transaction_date="20260912103000",
            create_date="20260913090000", ip_addr="127.0.0.1",
            order_info=REFUND_ORDER_INFO, full_refund=True,
        )


def test_default_transport_posts_json_with_correct_method_and_headers(monkeypatch):
    """Regression guard for requirement 'refund request uses POST JSON':
    the default transport must issue a real HTTP POST with a JSON body."""
    import app.integrations.vnpay as vnpay_module

    captured_request = {}

    class FakeHttpResponse:
        def __init__(self, body: bytes):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def read(self):
            return self._body

    def fake_urlopen(request, timeout=None):
        captured_request["method"] = request.get_method()
        captured_request["headers"] = dict(request.header_items())
        captured_request["body"] = json.loads(request.data.decode("utf-8"))
        response = _signed_refund_response()
        return FakeHttpResponse(json.dumps(response).encode("utf-8"))

    monkeypatch.setattr(vnpay_module, "urlopen", fake_urlopen)
    client = make_client()  # default transport = real _post_json
    client.refund(
        request_id=REFUND_REQUEST_ID, txn_ref=REFUND_TXN_REF, amount=60000,
        transaction_no="998877", transaction_date="20260912103000",
        create_date="20260913090000", ip_addr="127.0.0.1",
        order_info=REFUND_ORDER_INFO, full_refund=True,
    )

    assert captured_request["method"] == "POST"
    assert "application/json" in captured_request["headers"].get("Content-type", "")
    assert captured_request["body"]["vnp_Command"] == "refund"
    assert captured_request["body"]["vnp_SecureHash"] == FIXED_REFUND_REQUEST_DIGEST

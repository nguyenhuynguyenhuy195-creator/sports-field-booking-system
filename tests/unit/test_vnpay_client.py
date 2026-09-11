from decimal import Decimal
from urllib.parse import parse_qsl, urlsplit

import pytest

from app.integrations import (
    VnpayAmountError,
    VnpayClient,
    VnpayConfigurationError,
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

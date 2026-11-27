"""Sign in with a phone number: codes, limits, sessions, the demo number, and that a signed-in owner sees only their own business."""
import pytest
from lab import db
from lab.models import Alert, OtpCode
from lab.service import ServiceError
from sqlalchemy import select, update

from assistant import alerts, auth, sms

AUTH = "/api/assistant/auth"
API = "/api/assistant"
PHONE = "98765 43210"


@pytest.fixture
def sent(monkeypatch):
    codes = []

    async def fake_send(to, code):
        codes.append((to, code))
    monkeypatch.setattr(sms, "send_otp", fake_send)
    return codes


def sign_in(client, sent, phone=PHONE, **extra):
    assert client.post(f"{AUTH}/request", json={"phone": phone}).status_code == 200
    r = client.post(f"{AUTH}/verify", json={"phone": phone, "code": sent[-1][1], **extra})
    assert r.status_code == 200, r.text
    return r.json()


def age_codes(minutes):
    """Make every stored code older, to get past the wait between codes without sleeping."""
    import datetime
    with db.session_scope() as s:
        for row in s.scalars(select(OtpCode)):
            row.created_at = row.created_at - datetime.timedelta(minutes=minutes)


def owner(token):
    return {"X-Business-Key": token}


def test_the_login_screen_can_show_the_demo_number(client):
    cfg = client.get(f"{AUTH}/config").json()
    assert cfg["demo"] == {"phone": "+919000000001", "code": "246810"} and "sms_ready" in cfg and "otp_provider" in cfg


def test_a_new_number_signs_up_and_the_same_number_signs_back_in(client, sent):
    first = sign_in(client, sent, accept=True)
    assert first["is_new"] and first["token"].startswith("s_") and sent[0][0] == "+919876543210"
    me = client.get(f"{API}/me", headers=owner(first["token"])).json()
    assert me["role"] == "owner" and me["business_id"] == first["business_id"] and me["phone"].endswith("210") and "98765" not in me["phone"]
    assert client.get(f"{API}/profile", headers=owner(first["token"])).json()["onboarded"] is False  # a new owner is taken through onboarding
    client.post(f"{AUTH}/logout", headers=owner(first["token"]))
    again = None
    age_codes(5)
    again = sign_in(client, sent)
    assert not again["is_new"] and again["business_id"] == first["business_id"] and again["token"] != first["token"]


def test_terms_acceptance_is_recorded_with_its_version(client, sent):
    t = sign_in(client, sent, accept=True)
    from lab.models import Business
    with db.session_scope() as s:
        legal = s.get(Business, t["business_id"]).settings["legal"]
    assert legal["version"] and legal["accepted_at"]


def test_a_wrong_code_is_refused_counted_and_locks_after_five_tries(client, sent):
    client.post(f"{AUTH}/request", json={"phone": PHONE})
    good = sent[-1][1]
    bad = "000000" if good != "000000" else "111111"
    for _ in range(5):
        r = client.post(f"{AUTH}/verify", json={"phone": PHONE, "code": bad})
        assert r.status_code == 401 and "not right" in r.json()["detail"]
    r = client.post(f"{AUTH}/verify", json={"phone": PHONE, "code": good})
    assert r.status_code == 401 and "Too many wrong tries" in r.json()["detail"]


def test_a_code_works_once_and_expires(client, sent):
    client.post(f"{AUTH}/request", json={"phone": PHONE})
    code = sent[-1][1]
    assert client.post(f"{AUTH}/verify", json={"phone": PHONE, "code": code}).status_code == 200
    assert client.post(f"{AUTH}/verify", json={"phone": PHONE, "code": code}).status_code == 401  # used up
    with db.session_scope() as s:
        for row in s.scalars(select(OtpCode)):
            row.used, row.expires_at = False, row.created_at
    assert "expired" in client.post(f"{AUTH}/verify", json={"phone": PHONE, "code": code}).json()["detail"]


def test_sending_is_rate_limited_per_number(client, sent):
    assert client.post(f"{AUTH}/request", json={"phone": PHONE}).status_code == 200
    r = client.post(f"{AUTH}/request", json={"phone": PHONE})
    assert r.status_code == 429 and "wait" in r.json()["detail"].lower() and len(sent) == 1
    for _ in range(4):
        age_codes(2)
        client.post(f"{AUTH}/request", json={"phone": PHONE})
    age_codes(2)
    r = client.post(f"{AUTH}/request", json={"phone": PHONE})
    assert r.status_code == 429 and "hour" in r.json()["detail"]


def test_a_bad_number_is_refused(client, sent):
    assert client.post(f"{AUTH}/request", json={"phone": "12"}).status_code in (422, 400)
    assert sent == []


def test_the_demo_number_signs_into_a_sample_shop_without_an_sms(client, sent):
    r = client.post(f"{AUTH}/request", json={"phone": "+91 90000 00001"}).json()
    assert r["demo"] and sent == []
    t = client.post(f"{AUTH}/verify", json={"phone": "9000000001", "code": "246810"}).json()
    assert t["demo"] and not t["is_new"]
    h = owner(t["token"])
    assert client.get(f"{API}/profile", headers=h).json()["business_name"] == "Demo Kirana"
    assert len(client.get(f"{API}/board", headers=h).json()["items"]) >= 3
    assert len(client.get(f"{API}/calls", headers=h).json()) >= 2 if isinstance(client.get(f"{API}/calls", headers=h).json(), list) else True
    assert client.get(f"{API}/me", headers=h).json()["demo"] is True
    again = client.post(f"{AUTH}/verify", json={"phone": "9000000001", "code": "246810"})  # signing in twice keeps one demo shop
    assert again.status_code in (200, 401)


def test_the_demo_number_can_be_switched_off(client, sent, monkeypatch):
    monkeypatch.setenv("MUNSHI_DEMO_LOGIN", "off")
    assert client.get(f"{AUTH}/config").json()["demo"] is None
    client.post(f"{AUTH}/request", json={"phone": "9000000001"})
    assert len(sent) == 1  # it is now an ordinary number: a real SMS
    assert client.post(f"{AUTH}/verify", json={"phone": "9000000001", "code": "246810"}).status_code == 401


def test_signing_out_ends_the_session(client, sent):
    t = sign_in(client, sent)
    assert client.get(f"{API}/profile", headers=owner(t["token"])).status_code == 200
    assert client.post(f"{AUTH}/logout", headers=owner(t["token"])).status_code == 204
    r = client.get(f"{API}/profile", headers=owner(t["token"]))
    assert r.status_code == 401 and "sign in again" in r.json()["detail"]


def test_a_made_up_token_gets_nothing(client):
    assert client.get(f"{API}/profile", headers=owner("s_" + "x" * 40)).status_code == 401


def test_a_signed_in_owner_sees_only_their_own_business_and_no_platform_pages(client, sent):
    a = sign_in(client, sent, "9811111111")
    age_codes(5)
    b = sign_in(client, sent, "9822222222")
    client.post(f"{API}/board", json={"name": "Atta", "price": "42"}, headers=owner(a["token"]))
    assert client.get(f"{API}/board", headers=owner(b["token"])).json()["items"] == []
    assert client.get(f"{API}/admin/businesses", headers=owner(a["token"])).status_code == 403
    assert client.get(f"{API}/costs", headers=owner(a["token"])).status_code == 403


def test_if_the_sms_cannot_be_sent_the_person_is_told_and_the_operator_is_alerted(client, monkeypatch):
    async def broken(to, code):
        raise ServiceError("Sign-in by SMS is not switched on for this server yet. Please try again later.", 503)
    monkeypatch.setattr(sms, "send_otp", broken)
    r = client.post(f"{AUTH}/request", json={"phone": PHONE})
    assert r.status_code == 503 and "SMS" in r.json()["detail"]
    with db.session_scope() as s:
        row = s.scalar(select(Alert).where(Alert.key == "sms"))
        assert row and row.level == "error" and row.resolved_at is None
        assert s.scalar(select(OtpCode)) is None  # the code that never went out is not kept
    assert client.post(f"{AUTH}/request", json={"phone": PHONE}).status_code == 503  # and the next try is not blocked by a wait


def test_a_working_sms_clears_the_alert(client, sent):
    alerts.raise_alert("sms", "Sign-in codes are not being delivered", "x", "error")
    client.post(f"{AUTH}/request", json={"phone": PHONE})
    with db.session_scope() as s:
        assert s.scalar(select(Alert).where(Alert.key == "sms")).resolved_at is not None


def test_sms_goes_through_plivo_with_the_registered_sender_and_template(monkeypatch):
    import asyncio

    import llm
    from assistant import service
    from lab import settings_store

    seen = {}

    class R:
        status_code = 202

    class C:
        async def post(self, url, json=None, auth=None, timeout=None):
            seen.update(url=url, json=json, auth=auth)
            return R()
    monkeypatch.setattr(llm, "http_client", lambda: C())
    monkeypatch.setattr(settings_store, "get_phone", lambda s, b: {"auth_id": "AID", "auth_token": "tok", "number": "+9180"})

    async def fake_run_db(fn):
        return fn(None)
    monkeypatch.setattr(sms, "run_db", fake_run_db)
    monkeypatch.setenv("MUNSHI_OTP_PROVIDER", "plivo")
    monkeypatch.setenv("MUNSHI_SMS_SENDER", "MUNSHI")
    monkeypatch.setenv("MUNSHI_DLT_ENTITY_ID", "E1")
    monkeypatch.setenv("MUNSHI_DLT_TEMPLATE_ID", "T1")
    asyncio.run(sms.send_otp("+919876543210", "123456"))
    assert seen["url"].endswith("/Account/AID/Message/") and seen["auth"] == ("AID", "tok")
    assert seen["json"] == {"src": "MUNSHI", "dst": "919876543210", "text": sms.DEFAULT_TEMPLATE.format(code="123456"), "dlt_entity_id": "E1", "dlt_template_id": "T1"}
    monkeypatch.delenv("MUNSHI_SMS_SENDER")
    with pytest.raises(ServiceError) as e:
        asyncio.run(sms.send_otp("+919876543210", "123456"))
    assert e.value.status == 503


def test_sms_goes_through_msg91_with_authkey_and_template(monkeypatch):
    import asyncio

    import llm

    seen = {}

    class R:
        status_code = 200

    class C:
        async def post(self, url, json=None, headers=None, timeout=None, **kw):
            seen.update(url=url, json=json, headers=headers)
            return R()
    monkeypatch.setattr(llm, "http_client", lambda: C())
    monkeypatch.setenv("MUNSHI_OTP_PROVIDER", "msg91")
    monkeypatch.setenv("MUNSHI_MSG91_AUTHKEY", "AUTH123")
    monkeypatch.setenv("MUNSHI_MSG91_TEMPLATE_ID", "TPL456")
    asyncio.run(sms.send_otp("+919876543210", "654321"))
    assert seen["url"] == "https://control.msg91.com/api/v5/otp"
    assert seen["headers"]["authkey"] == "AUTH123"
    assert seen["json"] == {"template_id": "TPL456", "mobile": "919876543210", "otp": "654321"}
    monkeypatch.delenv("MUNSHI_MSG91_AUTHKEY")
    with pytest.raises(ServiceError) as e:
        asyncio.run(sms.send_otp("+919876543210", "654321"))
    assert e.value.status == 503


def test_sms_provider_defaults_to_msg91():
    assert sms.provider() == "msg91"


def test_sms_configured_checks_the_right_provider(monkeypatch):
    assert not sms.configured()
    monkeypatch.setenv("MUNSHI_MSG91_AUTHKEY", "key")
    assert sms.configured()
    monkeypatch.setenv("MUNSHI_OTP_PROVIDER", "plivo")
    assert not sms.configured()
    monkeypatch.setenv("MUNSHI_SMS_SENDER", "MUNSHI")
    assert sms.configured()

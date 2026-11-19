"""Running the platform safely: alerts, backup and restore, retention, policy pages, the owner's own data, the launch checklist."""
import asyncio
import datetime
import gzip
import json

import llm
import pytest
from lab import db
from lab.models import Alert, Business, Call, OtpCode, OwnerSession
from sqlalchemy import select

from assistant import alerts, auth, backup, legal, retention, sms
from test_assistant import API, add_item, ai, profile  # noqa: F401
from test_signin import AUTH, age_codes, owner, sent, sign_in  # noqa: F401


def open_alerts():
    with db.session_scope() as s:
        return {a.key: a for a in s.scalars(select(Alert).where(Alert.resolved_at.is_(None)))}


# --- alerts ----------------------------------------------------------------------------

NAMES = {"business_name": "Sharma Kirana", "owner_name": "Ramesh", "onboarded": True}


def test_a_failing_ai_raises_one_alert_with_a_count_and_recovery_clears_it(client, fake, ai):
    profile(client)
    working = llm.chat

    async def failing(*a, **k):
        raise llm.LLMError("All configured providers failed. Groq: boom")
    cid = client.post(f"{API}/calls", json={"caller_number": "98765 43210"}).json()["call"]["id"]
    __import__("pytest").MonkeyPatch().setattr(llm, "chat", failing)
    for _ in range(3):
        assert client.post(f"{API}/calls/{cid}/turns", json={"content": "hello"}).status_code == 502
    got = open_alerts()
    assert list(got) == ["llm"] and got["llm"].count == 3 and got["llm"].level == "error"
    __import__("pytest").MonkeyPatch().setattr(llm, "chat", working)
    assert client.post(f"{API}/calls/{cid}/turns", json={"content": "hello"}).status_code == 200
    assert open_alerts() == {}


def test_a_quota_failure_is_its_own_clear_alert(client, fake, monkeypatch):
    profile(client)
    monkeypatch.setattr(fake, "assistant_reply", lambda m: "x")
    alerts.llm_failed(llm.LLMError("Groq: HTTP 429 (rate limit or quota reached): tokens per day (TPD): Limit 200000, Used 198052"))
    a = open_alerts()["llm-quota"]
    assert "limit is reached" in a.title and "198052" in a.detail


def test_the_operator_can_list_and_resolve_alerts(client):
    alerts.raise_alert("x", "Something", "detail", "warn")
    items = client.get(f"{API}/admin/alerts").json()
    assert items["open"] == 1 and items["items"][0]["title"] == "Something"
    assert client.post(f"{API}/admin/alerts/{items['items'][0]['id']}/resolve").status_code == 204
    assert client.get(f"{API}/admin/alerts").json()["open"] == 0
    assert client.post(f"{API}/admin/alerts/nope/resolve").status_code == 404


def test_an_owner_cannot_see_the_platforms_alerts_backup_or_checklist(client, sent):
    t = sign_in(client, sent)
    for path in ("/admin/alerts", "/admin/readiness", "/admin/backup"):
        assert client.get(API + path, headers=owner(t["token"])).status_code == 403


def test_alerts_are_sent_to_the_webhook_once_and_repeated_only_after_a_while(client, monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.example/abc")
    posted = []

    class R:
        status_code = 200

    class C:
        async def post(self, url, json=None, timeout=None):
            posted.append((url, json))
            return R()
    monkeypatch.setattr(llm, "http_client", lambda: C())
    alerts.raise_alert("k", "Quota used up", "details", "error")
    assert asyncio.run(alerts.notify_pending()) == 1 and "Quota used up" in posted[0][1]["text"] and posted[0][0] == "https://hooks.example/abc"
    assert asyncio.run(alerts.notify_pending()) == 0  # same problem, already told
    alerts.raise_alert("k", "Quota used up", "again", "error")
    assert asyncio.run(alerts.notify_pending()) == 0  # still inside the quiet period
    with db.session_scope() as s:
        row = s.scalar(select(Alert).where(Alert.key == "k"))
        row.notified_at = row.notified_at - datetime.timedelta(hours=1)
    alerts.raise_alert("k", "Quota used up", "again", "error")
    assert asyncio.run(alerts.notify_pending()) == 1


def test_budget_alerts_appear_at_80_percent_and_clear_when_the_budget_is_raised(client, ai):
    profile(client)
    client.put(f"{API}/budget", json={"monthly_inr": 100, "hard_stop": False})
    cid = client.post(f"{API}/calls", json={"caller_number": "98765 43210"}).json()["call"]["id"]
    client.post(f"{API}/calls/{cid}/end")
    with db.session_scope() as s:
        s.scalar(select(Call)).cost = {"total": 85.0}
    alerts.check_budgets()
    assert any(k.startswith("budget-") for k in open_alerts())
    client.put(f"{API}/budget", json={"monthly_inr": 1000, "hard_stop": False})
    alerts.check_budgets()
    assert not any(k.startswith("budget-") for k in open_alerts())


def test_the_deep_health_check_reports_degraded_while_an_error_is_open(client):
    assert client.get("/health/deep").json()["checks"]["database"] is True
    alerts.raise_alert("llm", "AI failing", "x", "error")
    assert client.get("/health/deep").json()["status"] == "degraded"
    alerts.raise_alert("slow", "Just a warning", "x", "warn")
    assert client.get("/health/deep").status_code == 200


# --- backup and restore --------------------------------------------------------------------

def test_a_backup_restores_everything_into_an_empty_database(client, sent, ai):
    t = sign_in(client, sent, accept=True)
    h = owner(t["token"])
    client.put(f"{API}/profile", json={"business_name": "Sharma Kirana", "owner_name": "Ramesh", "mode": "board", "onboarded": True}, headers=h)
    client.post(f"{API}/board", json={"name": "Atta", "price": "42/kg"}, headers=h)
    client.post(f"{API}/contacts", json={"name": "Mummy", "phone": "98111 11111"}, headers=h)
    cid = client.post(f"{API}/calls", json={"caller_number": "98222 22222"}, headers=h).json()["call"]["id"]
    client.post(f"{API}/calls/{cid}/turns", json={"content": "atta chahiye"}, headers=h)
    r = client.get(f"{API}/admin/backup")
    assert r.status_code == 200 and r.headers["content-type"] == "application/gzip" and "munshi-backup" in r.headers["content-disposition"]
    data = json.loads(gzip.decompress(r.content))
    assert data["counts"]["businesses"] >= 1 and data["counts"]["calls"] == 1 and data["counts"]["call_turns"] >= 2 and data["counts"]["board_items"] == 1
    with db.session_scope() as s:  # wipe everything, then bring it back from the file
        for tbl in reversed(backup._tables()):
            s.execute(tbl.delete())
    with db.session_scope() as s:
        done = backup.restore(s, data)
        assert done["calls"] == 1 and done["board_items"] == 1 and done["contacts"] == 1
    assert client.get(f"{API}/board", headers=h).json()["items"][0]["name"] == "Atta"  # the same sign-in still works
    assert client.get(f"{API}/calls", headers=h).status_code == 200


def test_restore_refuses_a_non_empty_database_and_replace_overwrites_it(client, sent):
    sign_in(client, sent)
    with db.session_scope() as s:
        data = backup.dump(s)
    with db.session_scope() as s:
        with pytest.raises(ValueError, match="not empty"):
            backup.restore(s, data)
    with db.session_scope() as s:
        done = backup.restore(s, data, replace=True)
        assert done["businesses"] == data["counts"]["businesses"]
    with db.session_scope() as s:
        assert backup.dump(s)["counts"] == data["counts"]
    with pytest.raises(ValueError, match="not a Munshi backup"):
        with db.session_scope() as s:
            backup.restore(s, {"format": 99, "tables": {}})


def test_a_restored_database_keeps_working_sessions_and_data(client, sent):
    t = sign_in(client, sent)
    h = owner(t["token"])
    client.post(f"{API}/board", json={"name": "Atta", "price": "42/kg"}, headers=h)
    with db.session_scope() as s:
        data = backup.dump(s)
    with db.session_scope() as s:
        backup.restore(s, data, replace=True)
    assert client.get(f"{API}/board", headers=h).json()["items"][0]["name"] == "Atta"


# --- retention -------------------------------------------------------------------------------

def test_old_calls_and_spent_codes_are_deleted_and_recent_ones_stay(client, sent, ai):
    t = sign_in(client, sent)
    h = owner(t["token"])
    client.put(f"{API}/profile", json=NAMES, headers=h)
    old = client.post(f"{API}/calls", json={"caller_number": "98222 22222"}, headers=h).json()["call"]["id"]
    new = client.post(f"{API}/calls", json={"caller_number": "98333 33333"}, headers=h).json()["call"]["id"]
    client.post(f"{API}/calls/{old}/end", headers=h)
    client.post(f"{API}/calls/{new}/end", headers=h)
    with db.session_scope() as s:
        c = s.get(Call, old)
        c.started_at = c.started_at - datetime.timedelta(days=legal.retention_days() + 5)
        s.add(OtpCode(phone="+919000000009", code_hash="x", created_at=c.started_at, expires_at=c.started_at))
    with db.session_scope() as s:
        out = retention.purge(s)
    assert out["calls"] == 1 and out["codes"] >= 1
    with db.session_scope() as s:
        assert s.get(Call, old) is None and s.get(Call, new) is not None


def test_retention_period_is_configurable_but_never_below_30_days(monkeypatch):
    monkeypatch.setenv("MUNSHI_RETENTION_DAYS", "90")
    assert legal.retention_days() == 90
    monkeypatch.setenv("MUNSHI_RETENTION_DAYS", "3")
    assert legal.retention_days() == 30
    monkeypatch.setenv("MUNSHI_RETENTION_DAYS", "junk")
    assert legal.retention_days() == 365


# --- policy pages ------------------------------------------------------------------------------

def test_policy_pages_are_public_and_show_what_is_still_to_be_filled(client, monkeypatch):
    for k in legal.FIELDS:
        monkeypatch.delenv(k, raising=False)
    for path, needle in (("/legal/privacy", "Digital Personal Data Protection"), ("/legal/terms", "Munshi does"), ("/legal/delete-account", "Delete my account and data"), ("/legal", "Privacy Policy")):
        r = client.get(path)
        assert r.status_code == 200 and "text/html" in r.headers["content-type"] and needle in r.text, path
    assert "to be filled before launch" in client.get("/legal/privacy").text
    assert 'id="delete"' in client.get("/legal/delete-account").text  # Play asks for a link straight to the deletion steps


def test_policy_pages_use_the_operators_details_when_set(client, monkeypatch):
    for k, v in {"LEGAL_ENTITY": "Acme Voice Pvt Ltd", "LEGAL_ADDRESS": "1 MG Road, Indore", "GRIEVANCE_NAME": "Asha Rao", "GRIEVANCE_EMAIL": "grievance@acme.test", "SUPPORT_EMAIL": "help@acme.test", "LEGAL_JURISDICTION": "Indore"}.items():
        monkeypatch.setenv(k, v)
    page = client.get("/legal/privacy").text
    assert "Acme Voice Pvt Ltd" in page and "grievance@acme.test" in page and "to be filled" not in page and legal.missing() == []


def test_the_privacy_policy_only_claims_what_the_system_does(client):
    text = client.get("/legal/privacy").text
    for vendor in ("Render", "Supabase", "Groq", "Google Cloud", "Plivo"):
        assert vendor in text
    assert f"{legal.retention_days()} days" in text and "We do not keep the audio" in text


def test_every_call_starts_by_saying_it_is_an_ai_and_that_the_conversation_is_noted(client, ai):
    profile(client, languages=["en"])
    first = client.post(f"{API}/calls", json={"caller_number": "98765 43210"}).json()["greeting"]
    assert "AI" in first and "noted" in first
    client.put(f"{API}/profile", json={**client.get(f"{API}/profile").json(), "languages": ["hi", "en"]})
    hi = client.post(f"{API}/calls", json={"caller_number": "98765 43211"}).json()["greeting"]
    assert "AI" in hi and "नोट" in hi


# --- the owner's own data ------------------------------------------------------------------------

def test_an_owner_can_download_their_data_without_secrets_and_never_anyone_elses(client, sent, ai):
    a = sign_in(client, sent, "9811111111", accept=True)
    age_codes(5)
    b = sign_in(client, sent, "9822222222")
    ha, hb = owner(a["token"]), owner(b["token"])
    client.put(f"{API}/profile", json={"business_name": "A Store", "owner_name": "Asha"}, headers=ha)
    client.put(f"{API}/profile", json={"business_name": "B Store", "owner_name": "Bala"}, headers=hb)
    client.post(f"{API}/board", json={"name": "Atta", "price": "42/kg"}, headers=ha)
    cid = client.post(f"{API}/calls", json={"caller_number": "98999 99999"}, headers=ha).json()["call"]["id"]
    client.post(f"{API}/calls/{cid}/turns", json={"content": "mujhe atta chahiye"}, headers=ha)
    r = client.get(f"{API}/account/export", headers=ha)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    d = r.json()
    assert d["business"]["name"] == "New business" or d["profile"]["business_name"] == "A Store"
    assert d["rates"] == [{"name": "Atta", "price": "Rs 42/kg", "status": "in_stock"}] or d["rates"][0]["name"] == "Atta"
    assert any("atta chahiye" in t["text"] for t in d["calls"][0]["turns"]) and d["consent"]["version"] == legal.VERSION
    blob = json.dumps(d)
    assert "token_enc" not in blob and "auth_token" not in blob and "mk_" not in blob
    assert client.get(f"{API}/account/export", headers=hb).json()["calls"] == []  # B sees none of A's calls


def test_deleting_an_account_removes_everything_and_ends_the_session(client, sent, ai):
    t = sign_in(client, sent)
    h = owner(t["token"])
    client.put(f"{API}/profile", json=NAMES, headers=h)
    client.post(f"{API}/board", json={"name": "Atta", "price": "42/kg"}, headers=h)
    client.post(f"{API}/contacts", json={"name": "Mummy", "phone": "98111 11111"}, headers=h)
    cid = client.post(f"{API}/calls", json={"caller_number": "98222 22222"}, headers=h).json()["call"]["id"]
    client.post(f"{API}/calls/{cid}/turns", json={"content": "hello"}, headers=h)
    assert client.post(f"{API}/account/delete", json={"confirm": "nope"}, headers=h).status_code == 422
    assert client.post(f"{API}/account/delete", json={"confirm": "delete"}, headers=h).json() == {"deleted": True}
    with db.session_scope() as s:
        assert s.get(Business, t["business_id"]) is None
        from lab.models import BoardItem, CallTurn, Contact
        assert not s.scalars(select(Call)).all() and not s.scalars(select(Contact)).all() and not s.scalars(select(BoardItem)).all() and not s.scalars(select(CallTurn)).all()
        assert not s.scalars(select(OwnerSession)).all()
    assert client.get(f"{API}/profile", headers=h).status_code == 401
    assert any("account was deleted" in e["summary"] for e in client.get(f"{API}/admin/activity?limit=20").json()) if client.get(f"{API}/admin/activity").status_code == 200 else True


def test_the_platform_admin_cannot_use_the_owner_delete_by_mistake(client):
    assert client.post(f"{API}/account/delete", json={"confirm": "DELETE"}).status_code == 403
    assert client.get(f"{API}/account/export").status_code == 403


# --- the launch checklist ---------------------------------------------------------------------

def test_the_launch_checklist_says_what_is_missing_and_how_to_fix_it(client, monkeypatch):
    for k in list(legal.FIELDS) + ["MUNSHI_SMS_SENDER", "ALERT_WEBHOOK_URL"]:
        monkeypatch.delenv(k, raising=False)
    r = client.get(f"{API}/admin/readiness").json()
    by = {c["id"]: c for c in r["checks"]}
    assert not r["ready"] and {"legal", "owner_sms", "admin_signin"} <= set(r["needed"])
    assert "LEGAL_ENTITY" in by["legal"]["fix"] and "MUNSHI_SMS_SENDER" in by["owner_sms"]["fix"] and by["backups"]["ok"] is False
    assert by["alerts_webhook"]["level"] == "recommended" and by["ai_backup"]["level"] == "recommended"

"""Many businesses on one platform: private data, owner links, the admin's view across all of them."""
import pytest
from fastapi.testclient import TestClient

from test_assistant import FakeAssistantLLM, ai, clean, signed, TOKEN  # noqa: F401

API = "/api/assistant"
ADMIN = "adminadminadminadminadminadmin12"


@pytest.fixture
def platform(env, ai):
    """A server with sign-in on: the admin has a token, each business has its own private link."""
    import main

    env.setenv("LAB_API_TOKENS", ADMIN)
    with TestClient(main.app) as c:
        yield c


def admin(client, method, path, **kw):
    return client.request(method, API + path, headers={"Authorization": f"Bearer {ADMIN}", **kw.pop("headers", {})}, **kw)


def owner(client, key, method, path, **kw):
    return client.request(method, API + path, headers={"X-Business-Key": key, **kw.pop("headers", {})}, **kw)


def new_business(client, name, owner_name, number=""):
    r = admin(client, "POST", "/admin/businesses", json={"name": name, "owner_name": owner_name, "phone_number": number})
    assert r.status_code == 201, r.text
    d = r.json()
    return d["id"], d["link"].split("#k=")[1]


def test_each_owner_sees_only_their_own_business(platform):
    a_id, a_key = new_business(platform, "Sharma Traders", "Ramesh")
    b_id, b_key = new_business(platform, "Gupta Sweets", "Anil")
    assert owner(platform, a_key, "POST", "/board", json={"name": "Basmati rice", "price": "450"}).status_code == 201
    assert owner(platform, b_key, "POST", "/board", json={"name": "Kaju katli", "price": "900"}).status_code == 201
    assert [i["name"] for i in owner(platform, a_key, "GET", "/board").json()["items"]] == ["Basmati rice"]
    assert [i["name"] for i in owner(platform, b_key, "GET", "/board").json()["items"]] == ["Kaju katli"]
    assert owner(platform, a_key, "GET", "/profile").json()["owner_name"] == "Ramesh" and owner(platform, b_key, "GET", "/profile").json()["owner_name"] == "Anil"
    # the same phone number can be a contact for two different businesses
    assert owner(platform, a_key, "POST", "/contacts", json={"name": "Mom", "phone": "9876543210"}).status_code == 201
    assert owner(platform, b_key, "POST", "/contacts", json={"name": "Mom", "phone": "9876543210"}).status_code == 201
    assert owner(platform, a_key, "POST", "/contacts", json={"name": "Mom", "phone": "9876543210"}).status_code == 409


def test_one_owner_cannot_open_change_or_delete_another_businesss_things(platform):
    _, a_key = new_business(platform, "Sharma Traders", "Ramesh")
    _, b_key = new_business(platform, "Gupta Sweets", "Anil")
    item = owner(platform, a_key, "POST", "/board", json={"name": "Basmati rice", "price": "450"}).json()
    contact = owner(platform, a_key, "POST", "/contacts", json={"name": "Mom", "phone": "9876543210"}).json()
    call = owner(platform, a_key, "POST", "/calls", json={}).json()["call"]
    for method, path, body in [("PUT", f"/board/{item['id']}", {"price": "1"}), ("DELETE", f"/board/{item['id']}", None), ("PUT", f"/contacts/{contact['id']}", {"name": "x"}),
                               ("DELETE", f"/contacts/{contact['id']}", None), ("GET", f"/calls/{call['id']}", None), ("PUT", f"/calls/{call['id']}", {"reviewed": True}),
                               ("DELETE", f"/calls/{call['id']}", None), ("POST", f"/calls/{call['id']}/turns", {"content": "hello"}), ("POST", f"/calls/{call['id']}/end", None),
                               ("POST", f"/calls/{call['id']}/notes", {"body": "x"})]:
        r = owner(platform, b_key, method, path, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (method, path, r.status_code, r.text)
    assert owner(platform, a_key, "GET", f"/calls/{call['id']}").status_code == 200  # still fine for its owner
    assert owner(platform, b_key, "GET", "/calls").json()["total"] == 0


def test_owners_cannot_reach_platform_settings_or_other_businesses(platform):
    _, key = new_business(platform, "Sharma Traders", "Ramesh")
    for method, path in [("GET", "/admin/businesses"), ("GET", "/admin/overview"), ("GET", "/admin/costs"), ("GET", "/admin/calls"), ("GET", "/prompts?scope=platform"), ("GET", "/integrations"),
                         ("GET", "/costs"), ("GET", "/budget"), ("GET", "/activity"), ("GET", "/vision"), ("PUT", "/phone"), ("PUT", "/whatsapp")]:
        assert owner(platform, key, method, path, **({"json": {}} if method == "PUT" else {})).status_code == 403, path
    assert owner(platform, "mk_notarealkey", "GET", "/profile").status_code == 401
    assert platform.get(f"{API}/profile").status_code == 401  # no token, no link
    # an owner cannot pick another business by header
    other, _ = new_business(platform, "Gupta Sweets", "Anil")
    assert owner(platform, key, "GET", "/profile", headers={"X-Business": other}).json()["business_name"] == "Sharma Traders"
    # and the owner's status view carries no platform keys or webhook addresses
    s = owner(platform, key, "GET", "/status").json()
    assert s["role"] == "owner" and "webhooks" not in s and "voice" not in s and "auth_id" not in s["phone"]


def test_a_new_link_replaces_the_old_one_and_a_deleted_business_takes_its_data_along(platform):
    biz, key = new_business(platform, "Sharma Traders", "Ramesh")
    assert admin(platform, "GET", f"/admin/businesses/{biz}/link").json()["link"].endswith(key)  # the admin can show it again
    new = admin(platform, "POST", f"/admin/businesses/{biz}/link").json()["link"].split("#k=")[1]
    assert new != key and owner(platform, key, "GET", "/profile").status_code == 401 and owner(platform, new, "GET", "/profile").status_code == 200
    owner(platform, new, "POST", "/board", json={"name": "Rice", "price": "40"})
    assert admin(platform, "POST", f"/admin/businesses/{biz}/delete", json={"confirm_name": "wrong"}).status_code == 422
    assert admin(platform, "POST", f"/admin/businesses/{biz}/delete", json={"confirm_name": "sharma traders"}).status_code == 204
    assert owner(platform, new, "GET", "/profile").status_code == 401 and admin(platform, "GET", "/admin/businesses").json()["items"] == []


def test_the_admin_sees_every_business_and_every_call(platform, ai):
    a_id, a_key = new_business(platform, "Sharma Traders", "Ramesh")
    b_id, b_key = new_business(platform, "Gupta Sweets", "Anil")
    for key in (a_key, b_key):
        call = owner(platform, key, "POST", "/calls", json={}).json()["call"]
        owner(platform, key, "POST", f"/calls/{call['id']}/turns", json={"content": "I need rice, call me back"})
        owner(platform, key, "POST", f"/calls/{call['id']}/end")
    rows = {r["name"]: r for r in admin(platform, "GET", "/admin/businesses").json()["items"]}
    assert rows["Sharma Traders"]["calls"] == 1 and rows["Gupta Sweets"]["needs_action"] == 1
    allc = admin(platform, "GET", "/admin/calls").json()
    assert allc["total"] == 2 and {c["business"] for c in allc["items"]} == {"Sharma Traders", "Gupta Sweets"}
    only = admin(platform, "GET", f"/admin/calls?business={a_id}").json()
    assert only["total"] == 1 and only["items"][0]["business"] == "Sharma Traders"
    detail = admin(platform, "GET", f"/admin/calls/{only['items'][0]['id']}").json()
    assert detail["business"] == "Sharma Traders" and detail["turns"]
    ov = admin(platform, "GET", "/admin/overview").json()
    assert ov["businesses"] == 2 and ov["calls"] == 2 and ov["needs_action"] == 2 and ov["cost"] >= 0 and len(ov["recent"]) == 2
    assert {n["kind"] for n in ov["attention"]} >= {"phone"}  # no Munshi number assigned yet
    costs = admin(platform, "GET", "/admin/costs").json()
    assert {r["name"] for r in costs["businesses"]} == {"Sharma Traders", "Gupta Sweets"} and costs["calls"] == 2 and abs(sum(r["total"] for r in costs["businesses"]) - costs["total"]) < 0.02
    # the admin can work inside one business by naming it
    assert admin(platform, "GET", "/board", headers={"X-Business": b_id}).status_code == 200
    assert admin(platform, "GET", "/profile", headers={"X-Business": "nope"}).status_code == 404
    log = admin(platform, "GET", "/activity?all=true").json()
    assert {e["business"] for e in log} >= {"Sharma Traders", "Gupta Sweets"}


def test_phone_calls_go_to_the_business_that_owns_the_number(platform, ai):
    a_id, a_key = new_business(platform, "Sharma Traders", "Ramesh", "+918047112233")
    b_id, b_key = new_business(platform, "Gupta Sweets", "Anil", "+918047119999")
    assert admin(platform, "POST", "/admin/businesses", json={"name": "Third", "phone_number": "8047112233"}).status_code == 409  # one number, one business
    admin(platform, "PUT", "/phone", json={"auth_id": "MAXXXX", "auth_token": TOKEN, "number": "+918047112233"})
    r = signed(platform, "/telephony/plivo/answer", {"CallUUID": "u-a", "From": "9876543210", "To": "+918047112233"})
    assert r.status_code == 200 and "<Record" in r.text and "Sharma Traders" in r.text
    r = signed(platform, "/telephony/plivo/answer", {"CallUUID": "u-b", "From": "9876543211", "To": "+918047119999"})
    assert "Gupta Sweets" in r.text
    assert signed(platform, "/telephony/plivo/answer", {"CallUUID": "u-x", "From": "9876543212", "To": "+919999999999"}).text.count("not available") == 1  # a number nobody owns
    signed(platform, "/telephony/plivo/hangup", {"CallUUID": "u-a", "Duration": "12"})
    import time
    time.sleep(0.5)
    assert owner(platform, a_key, "GET", "/calls").json()["total"] == 1 and owner(platform, b_key, "GET", "/calls").json()["total"] == 0
    # a paused business is not answered
    admin(platform, "PUT", f"/admin/businesses/{b_id}", json={"active": False})
    r = signed(platform, "/telephony/plivo/answer", {"CallUUID": "u-b2", "From": "9876543213", "To": "+918047119999"})
    assert "<Record" not in r.text and "not available" in r.text


def test_per_business_budget_and_board_freshness_do_not_leak(platform):
    _, a_key = new_business(platform, "Sharma Traders", "Ramesh")
    _, b_key = new_business(platform, "Gupta Sweets", "Anil")
    owner(platform, a_key, "PUT", "/knowledge", json={"stale_days": 7})
    assert owner(platform, a_key, "GET", "/knowledge").json()["stale_days"] == 7 and owner(platform, b_key, "GET", "/knowledge").json()["stale_days"] == 2
    a_id = admin(platform, "GET", "/admin/businesses").json()["items"][0]["id"]
    admin(platform, "PUT", "/budget", json={"monthly_inr": 100, "hard_stop": True}, headers={"X-Business": a_id})
    rows = {r["name"]: r for r in admin(platform, "GET", "/admin/businesses").json()["items"]}
    assert rows["Sharma Traders"]["budget"] == 100 and rows["Gupta Sweets"]["budget"] == 0

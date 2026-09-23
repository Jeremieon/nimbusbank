"""Happy path: a same-user, same-currency transfer actually moves money. We
read both balances before and after and assert the exact delta, proving the
transfers-service -> accounts-service /internal/apply-transfer path works."""


def _balance(client, headers, account_id):
    r = client.get(f"/api/accounts/accounts/{account_id}", headers=headers)
    assert r.status_code == 200
    return r.json()["balance_cents"]


def test_same_user_transfer_moves_balances(client, alice):
    h = alice["headers"]
    before_from = _balance(client, h, 3)  # alice checking (USD)
    before_to = _balance(client, h, 4)    # alice savings  (USD)

    r = client.post("/api/transfers/transfers", headers=h, json={
        "from_account_id": 3, "to_account_id": 4, "amount_cents": 5000, "memo": "same ccy",
    })
    assert r.status_code == 201
    assert r.json()["status"] == "completed"

    after_from = _balance(client, h, 3)
    after_to = _balance(client, h, 4)
    assert after_from == before_from - 5000
    assert after_to == before_to + 5000

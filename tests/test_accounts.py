"""Happy path: a customer lists their own (correctly-scoped) accounts and
downloads the benign default statement."""

from conftest import ACCOUNTS


def test_list_own_accounts_is_scoped(client, alice):
    r = client.get("/api/accounts/accounts", headers=alice["headers"])
    assert r.status_code == 200
    accts = r.json()
    assert sorted(a["id"] for a in accts) == list(ACCOUNTS["alice"])  # [3, 4]
    for a in accts:
        assert a["user_id"] == alice["user_id"]


def test_statement_download_returns_csv(client, alice):
    r = client.get("/api/accounts/accounts/3/statement", headers=alice["headers"])
    assert r.status_code == 200
    assert r.text.strip()  # non-empty
    assert "," in r.text  # the benign default statement is CSV

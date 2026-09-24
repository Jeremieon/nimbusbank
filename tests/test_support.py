"""Happy path: a customer opens a ticket, reads their own ticket back, and
posts a follow-up message. Uses a throwaway user so seeded tickets stay clean."""


def test_create_read_and_post_message(client, throwaway):
    h = throwaway["headers"]

    cr = client.post("/api/support/tickets", headers=h,
                     json={"subject": "Need help", "body": "Hello support"})
    assert cr.status_code == 201
    ticket = cr.json()
    assert ticket["user_id"] == throwaway["user_id"]
    tid = ticket["id"]
    assert ticket["messages"][0]["body"] == "Hello support"

    g = client.get(f"/api/support/tickets/{tid}", headers=h)
    assert g.status_code == 200
    assert g.json()["id"] == tid

    pm = client.post(f"/api/support/tickets/{tid}/messages", headers=h,
                     json={"sender": "customer", "body": "another message"})
    assert pm.status_code == 201

    g2 = client.get(f"/api/support/tickets/{tid}", headers=h)
    bodies = [m["body"] for m in g2.json()["messages"]]
    assert "another message" in bodies

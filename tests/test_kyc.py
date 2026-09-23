"""Happy path: a customer uploads a benign document, lists their own docs, and
downloads the file back. Uses a throwaway user so no seeded doc is touched."""


def test_upload_list_download_roundtrip(client, throwaway):
    h = throwaway["headers"]
    content = b"hello kyc world"
    files = {"file": ("benign.txt", content, "text/plain")}
    data = {"doc_type": "id_card"}

    up = client.post("/api/kyc/kyc/upload", headers=h, files=files, data=data)
    assert up.status_code == 201
    doc = up.json()
    assert doc["user_id"] == throwaway["user_id"]
    assert doc["doc_type"] == "id_card"
    doc_id = doc["id"]

    lst = client.get("/api/kyc/kyc/documents", headers=h)
    assert lst.status_code == 200
    assert any(d["id"] == doc_id for d in lst.json())

    dl = client.get(f"/api/kyc/kyc/{doc_id}/download", headers=h)
    assert dl.status_code == 200
    assert dl.content == content

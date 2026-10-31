from app.services import backup as backup_svc
from tests.conftest import login


def test_system_info(seeded):
    client, admin = seeded
    r = client.get("/api/system/info", headers=admin)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["version"] and d["db_size_bytes"] > 0
    assert d["lan_enabled"] is False
    assert isinstance(d["lan_ips"], list)


def test_backups_create_list_download(seeded):
    client, admin = seeded
    r = client.post("/api/system/backups", headers=admin)
    assert r.status_code == 200, r.text
    name = r.json()["name"]
    assert r.json()["label"] == "manual" and r.json()["size_bytes"] > 0
    names = [b["name"] for b in client.get("/api/system/backups", headers=admin).json()]
    assert name in names
    dl = client.get(f"/api/system/backups/{name}/download", headers=admin)
    assert dl.status_code == 200 and dl.content[:15] == b"SQLite format 3"
    assert client.get("/api/system/backups/nope.db/download", headers=admin).status_code == 404
    audit = client.get("/api/system/audit", params={"limit": 20}, headers=admin).json()
    assert any(a["entity"] == "backup" and a["user_name"] == "Admin" for a in audit)


def test_restore_rejects_invalid_names(seeded):
    client, admin = seeded
    for bad in ("../dev.db", "..\\test.db", "test.db", "cafeteria-x.db", "/etc/passwd", "backups/../../test.db"):
        r = client.post("/api/system/restore", json={"name": bad}, headers=admin)
        assert r.status_code == 400, bad


def test_restore_valid_backup(seeded):
    client, admin = seeded
    name = client.post("/api/system/backups", headers=admin).json()["name"]
    r = client.post("/api/system/restore", json={"name": name}, headers=admin)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["restart_required"] is True and d["restored"] == name
    assert "pre-restore" in d["safety_backup"]
    assert any(p.name == d["safety_backup"] for p in backup_svc.list_backups())
    # App still works after restore
    assert client.get("/api/system/info", headers=admin).status_code == 200


def test_system_is_admin_only(seeded):
    client, _ = seeded
    h = login(client, "Encargado Demo", "3333")
    assert client.get("/api/system/info", headers=h).status_code == 403
    assert client.post("/api/system/backups", headers=h).status_code == 403
    assert client.post("/api/system/restore", json={"name": "x"}, headers=h).status_code == 403
    assert client.get("/api/system/audit", headers=h).status_code == 403


def test_lan_qr(seeded):
    client, admin = seeded
    r = client.get("/api/system/lan-qr", headers=admin)
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert r.headers["content-type"] == "image/png" and r.content[:8] == b"\x89PNG\r\n\x1a\n"

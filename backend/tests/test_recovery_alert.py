"""After a damaged database was restored from a backup, who manages backups gets a notice («Restauramos la copia del día X»)
in the bell and in Avisos, once; the others don't see it."""
from app.main import _recovery_alert
from tests.conftest import login

RECOVERY = {"backup": "cafeteria-20261115-182100-auto.db", "reason": "startup check", "at": "2026-11-16T09:00:00"}


def test_the_recovery_leaves_a_notice_for_who_manages_the_system(seeded, db):
    client, admin = seeded
    _recovery_alert(db, RECOVERY)
    db.commit()
    _recovery_alert(db, RECOVERY)  # the same start twice doesn't repeat it
    db.commit()
    mine = [a for a in client.get("/api/alerts", headers=admin).json() if a["type"] == "db_recovered"]
    assert len(mine) == 1
    assert mine[0]["title"] == "Restauramos la copia del 15/11 a las 18:21" and mine[0]["severity"] == "critical"
    # It is read once: it stops being active.
    assert client.post(f"/api/alerts/{mine[0]['id']}/read", headers=admin).status_code == 200
    # The cashier has no system.manage: not for them.
    caja = login(client, "Caja Demo", "1111")
    assert not [a for a in client.get("/api/alerts", headers=caja).json() if a["type"] == "db_recovered"]

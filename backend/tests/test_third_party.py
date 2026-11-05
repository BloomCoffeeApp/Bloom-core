"""Third-party notices: the build script (build/third_party_notices.py) and the About screen endpoint."""

import importlib.util
import json
from pathlib import Path

import pytest

from app.services import third_party

SCRIPT = Path(__file__).resolve().parents[2] / "build" / "third_party_notices.py"


@pytest.fixture(scope="module")
def tpn():
    spec = importlib.util.spec_from_file_location("third_party_notices", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_frontend(tmp_path: Path, tpn, monkeypatch) -> None:
    fe = tmp_path / "frontend"
    (fe / "src").mkdir(parents=True)
    (fe / "src" / "index.css").write_text('@import "tailwindcss";\n@import "@fontsource-variable/inter";\n@import "./local.css";\n')
    nm = fe / "node_modules"
    pkgs = {
        "react": ("19.0.0", "MIT", "MIT License\n\nCopyright (c) Meta Platforms, Inc. and affiliates.\n"),
        "lucide-react": ("1.0.0", "ISC", "ISC License\n\nCopyright (c) 2026 Lucide Icons and Contributors\n"),
        "tailwindcss": ("4.0.0", "MIT", "MIT License\n\nCopyright (c) Tailwind Labs, Inc.\n"),
        "@fontsource-variable/inter": ("5.0.0", "OFL-1.1", "Copyright 2016 The Inter Project Authors\n\nSIL OPEN FONT LICENSE Version 1.1\n"),
        "evil-gpl": ("1.0.0", "GPL-3.0-only", "GNU GENERAL PUBLIC LICENSE\n"),
        "no-text": ("1.0.0", "MIT", None),
    }
    for name, (version, lic, text) in pkgs.items():
        d = nm / name
        d.mkdir(parents=True)
        (d / "package.json").write_text(json.dumps({"name": name, "version": version, "license": lic}))
        if text:
            (d / "LICENSE").write_text(text)
    bundled = nm / ".cache" / "bloom" / "bundled-packages.json"
    bundled.parent.mkdir(parents=True)
    bundled.write_text(json.dumps(["react", "lucide-react", "evil-gpl", "no-text"]))
    monkeypatch.setattr(tpn, "FRONTEND", fe)
    monkeypatch.setattr(tpn, "BUNDLED_LIST", bundled)


def test_frontend_lists_bundle_plus_css_imports(tmp_path, tpn, monkeypatch):
    _fake_frontend(tmp_path, tpn, monkeypatch)
    pkgs = {p["name"]: p for p in tpn.frontend_packages()}
    # Bundle (Vite plugin) + CSS @imports (Tailwind, fonts); relative imports ignored.
    assert set(pkgs) == {"react", "lucide-react", "evil-gpl", "no-text", "tailwindcss", "@fontsource-variable/inter"}
    assert pkgs["lucide-react"]["license"] == "ISC"
    assert pkgs["lucide-react"]["copyright"] == ["Copyright (c) 2026 Lucide Icons and Contributors"]
    assert pkgs["@fontsource-variable/inter"]["license"] == "OFL-1.1"
    assert "SIL OPEN FONT LICENSE" in pkgs["@fontsource-variable/inter"]["text"]
    assert pkgs["evil-gpl"]["copyleft"] is True
    assert pkgs["react"]["copyleft"] is False
    # MIT without a LICENSE file: the standard text is reproduced and explained.
    assert "Permission is hereby granted" in pkgs["no-text"]["text"]
    assert pkgs["no-text"]["note"]


def test_backend_closure_follows_pyproject_and_skips_spec_excludes(tpn):
    pkgs = {p["name"].lower(): p for p in tpn.backend_packages()}
    for name in ("fastapi", "starlette", "pydantic", "sqlalchemy", "uvicorn", "pywebview", "cryptography", "pillow"):
        assert name in pkgs, name
    assert pkgs["fastapi"]["license"] == "MIT"
    assert pkgs["fastapi"]["text"]
    # Dev/build-only or excluded in cafeteria.spec: never listed as shipped.
    for name in ("pytest", "pyinstaller", "websockets", "httptools", "watchfiles", "pyyaml", "cython", "httpx"):
        assert name not in pkgs, name


def test_guess_license_from_text(tpn):
    assert tpn._guess_from_text("MIT License\nPermission is hereby granted, free of charge, to any") == "MIT"
    assert tpn._guess_from_text("Redistribution and use in source and binary forms ... Neither the name") == "BSD-3-Clause"
    assert tpn._guess_from_text("Permission to use, copy, modify, and/or distribute this software") == "ISC"
    assert tpn._guess_from_text("something else") == ""


def test_main_writes_files_and_flags_copyleft(tmp_path, tpn, monkeypatch, capsys):
    _fake_frontend(tmp_path, tpn, monkeypatch)
    out = tmp_path / "out"
    assert tpn.main(["--out", str(out)]) == 0
    data = json.loads((out / "third_party_notices.json").read_text(encoding="utf-8"))
    names = {p["name"] for p in data["packages"]}
    assert {"Python (CPython)", "fastapi", "react", "@fontsource-variable/inter"} <= names
    flagged = {f["name"] for f in data["flagged"]}
    assert "evil-gpl" in flagged
    assert "PyInstaller bootloader" in flagged  # GPL with the bootloader exception: reported, not fatal
    text = (out / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in text and "Licencia: ISC" in text
    assert "ATENCIÓN evil-gpl" in capsys.readouterr().out
    assert tpn.main(["--out", str(out), "--strict"]) == 1


def test_endpoint_without_generated_file(seeded, monkeypatch, tmp_path):
    client, admin = seeded
    monkeypatch.setattr(third_party, "notices_path", lambda: tmp_path / "missing.json")
    r = client.get("/api/system/third-party-licenses", headers=admin)
    assert r.status_code == 200
    assert r.json() == {"available": False, "generated_at": None, "packages": []}


def test_endpoint_serves_generated_file_to_any_user(seeded, monkeypatch, tmp_path):
    client, admin = seeded
    f = tmp_path / "third_party_notices.json"
    f.write_text(json.dumps({"generated_at": "2026-11-05T00:00:00+00:00", "packages": [
        {"name": "zod", "version": "1", "license": "MIT", "source": "frontend", "text": "MIT"},
        {"name": "Alembic", "version": "1", "license": "MIT", "source": "backend", "copyright": ["Copyright 2020 X"]},
    ]}), encoding="utf-8")
    monkeypatch.setattr(third_party, "notices_path", lambda: f)
    assert client.get("/api/system/third-party-licenses").status_code == 401
    r = client.get("/api/system/third-party-licenses", headers=admin)
    body = r.json()
    assert body["available"] is True
    assert [p["name"] for p in body["packages"]] == ["Alembic", "zod"]  # sorted, case-insensitive
    assert body["packages"][0]["copyright"] == ["Copyright 2020 X"]

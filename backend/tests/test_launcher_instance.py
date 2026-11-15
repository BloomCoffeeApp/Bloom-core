"""The desktop launcher serves each data folder from ONE process: a second launch only opens a window
(two servers migrating and writing the same SQLite file is how a database gets damaged)."""

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def launcher(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    mod = importlib.import_module("launcher")
    monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
    monkeypatch.setattr(mod, "_instance_lock", None)
    yield mod
    if mod._instance_lock is not None:
        mod._instance_lock.close()


def test_second_process_cannot_take_the_same_data_folder(launcher, tmp_path):
    assert launcher.acquire_instance_lock() is True
    first = launcher._instance_lock
    launcher._instance_lock = None
    try:
        assert launcher.acquire_instance_lock() is False  # another handle = another process for the lock
    finally:
        first.close()
    assert launcher.acquire_instance_lock() is True  # released when the holder goes away


def test_instance_port_round_trip(launcher):
    assert launcher.running_instance_port() is None
    launcher.write_instance_port(47861)
    assert launcher.running_instance_port() == 47861


def test_startup_error_page_explains_and_points_to_the_log(launcher, tmp_path):
    html = launcher.startup_error_html()
    assert "Bloom no pudo arrancar" in html and "app.log" in html and "backups" in html
    assert "<script" not in html


@pytest.mark.skipif(sys.platform != "win32", reason="the lock is a Windows byte-range lock here")
def test_lock_file_is_reused_not_recreated(launcher, tmp_path):
    assert launcher.acquire_instance_lock()
    assert (tmp_path / "instance.lock").exists()

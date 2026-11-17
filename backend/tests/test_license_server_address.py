"""Which license server the app talks to: the BLOOM_LICENSE_SERVER variable when it is set (even empty), else brand.json."""

from app.config import BRAND
from app.licensing.client import server_url


def test_brand_json_applies_only_when_the_variable_is_not_set(monkeypatch):
    monkeypatch.setitem(BRAND, "licenseServer", "https://licencias.example.com/")
    monkeypatch.delenv("BLOOM_LICENSE_SERVER", raising=False)
    assert server_url() == "https://licencias.example.com"


def test_an_empty_variable_means_no_server_even_with_an_address_in_brand_json(monkeypatch):
    # The e2e stack runs with BLOOM_LICENSE_SERVER="" to get the "this install has no server" screens.
    monkeypatch.setitem(BRAND, "licenseServer", "https://licencias.example.com")
    monkeypatch.setenv("BLOOM_LICENSE_SERVER", "")
    assert server_url() is None


def test_the_variable_overrides_brand_json_and_only_http_is_accepted(monkeypatch):
    monkeypatch.setitem(BRAND, "licenseServer", "https://licencias.example.com")
    monkeypatch.setenv("BLOOM_LICENSE_SERVER", "https://otro.example.com/")
    assert server_url() == "https://otro.example.com"
    monkeypatch.setenv("BLOOM_LICENSE_SERVER", "file:///etc/passwd")
    assert server_url() is None

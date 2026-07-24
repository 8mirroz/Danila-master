"""
Unit tests for my-crawler main.py helpers.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawlee import Request

from my_crawler.main import (
    get_browser_profile_dir,
    get_proxy_config_for_site,
    partition_requests_by_site,
)


def test_partition_requests_by_site_groups_known_labels():
    requests = [
        Request.from_url("https://www.exist.ru/Price/?pcode=OC90", label="exist"),
        Request.from_url("https://www.autodoc.ru/", label="autodoc"),
        Request.from_url("https://sochi.rossko.ru/search?q=oc90", label="rossko"),
        Request.from_url("https://example.com/", label="other"),
    ]

    batches = partition_requests_by_site(requests)

    assert [req.label for req in batches["exist"]] == ["exist"]
    assert [req.label for req in batches["autodoc"]] == ["autodoc"]
    assert [req.label for req in batches["rossko"]] == ["rossko"]


def test_get_browser_profile_dir_prefers_site_specific_override(monkeypatch, tmp_path):
    shared = tmp_path / "shared-profile"
    rossko = tmp_path / "rossko-profile"
    monkeypatch.setenv("BROWSER_PROFILE_DIR", str(shared))
    monkeypatch.setenv("ROSSKO_BROWSER_PROFILE_DIR", str(rossko))

    resolved = get_browser_profile_dir("rossko")

    assert resolved == str(rossko.resolve())
    assert os.path.isdir(resolved)


def test_get_proxy_config_for_site_prefers_site_specific_override(monkeypatch):
    monkeypatch.setenv("PROXY_URL", "http://shared:8080")
    monkeypatch.setenv("ROSSKO_PROXY_URL", "http://rossko:8080")

    assert get_proxy_config_for_site("rossko") == {"server": "http://rossko:8080"}
    assert get_proxy_config_for_site("autodoc") == {"server": "http://shared:8080"}

"""Tests for configuration resolution — profile precedence, proxy overrides."""

import os
from my_crawler.main import get_browser_profile_dir, get_proxy_config_for_site, get_proxy_config


class TestProfilePrecedence:
    def tear_method(self):
        for key in ["BROWSER_PROFILE_DIR", "EXIST_BROWSER_PROFILE_DIR",
                     "AUTODOC_BROWSER_PROFILE_DIR", "ROSSKO_BROWSER_PROFILE_DIR"]:
            os.environ.pop(key, None)

    def test_shared_profile_used_when_no_site_specific(self):
        os.environ["BROWSER_PROFILE_DIR"] = "/tmp/shared-profile"
        os.environ.pop("EXIST_BROWSER_PROFILE_DIR", None)
        profile = get_browser_profile_dir("exist")
        assert "/tmp/shared-profile" in profile
        self.tear_method()

    def test_site_specific_overrides_shared(self):
        os.environ["BROWSER_PROFILE_DIR"] = "/tmp/shared-profile"
        os.environ["EXIST_BROWSER_PROFILE_DIR"] = "/tmp/exist-specific"
        profile = get_browser_profile_dir("exist")
        assert "/tmp/exist-specific" in profile
        assert "/tmp/shared-profile" not in profile
        self.tear_method()

    def test_different_sites_get_different_profiles(self):
        os.environ["EXIST_BROWSER_PROFILE_DIR"] = "/tmp/exist-profile"
        os.environ["AUTODOC_BROWSER_PROFILE_DIR"] = "/tmp/autodoc-profile"
        exist_profile = get_browser_profile_dir("exist")
        autodoc_profile = get_browser_profile_dir("autodoc")
        assert "/tmp/exist-profile" in exist_profile
        assert "/tmp/autodoc-profile" in autodoc_profile
        self.tear_method()

    def test_fallback_to_default_when_no_env(self):
        os.environ.pop("BROWSER_PROFILE_DIR", None)
        os.environ.pop("EXIST_BROWSER_PROFILE_DIR", None)
        profile = get_browser_profile_dir("exist")
        assert ".browser-profile" in profile
        self.tear_method()


class TestProxyPrecedence:
    def tear_method(self):
        for key in ["PROXY_URL", "EXIST_PROXY_URL"]:
            os.environ.pop(key, None)

    def test_global_proxy_used_when_no_site_specific(self):
        os.environ["PROXY_URL"] = "http://global:proxy@host:8080"
        os.environ.pop("EXIST_PROXY_URL", None)
        config = get_proxy_config_for_site("exist")
        assert config is not None
        assert "global:proxy@host:8080" in config["server"]
        self.tear_method()

    def test_site_specific_proxy_overrides_global(self):
        os.environ["PROXY_URL"] = "http://global:proxy@host:8080"
        os.environ["EXIST_PROXY_URL"] = "http://exist:proxy@host:9090"
        config = get_proxy_config_for_site("exist")
        assert config is not None
        assert "exist:proxy@host:9090" in config["server"]
        assert "global" not in config["server"]
        self.tear_method()

    def test_rossko_proxy_hook(self):
        os.environ["ROSSKO_PROXY_URL"] = "http://rossko:proxy@host:7070"
        config = get_proxy_config_for_site("rossko")
        assert config is not None
        assert "rossko:proxy@host:7070" in config["server"]
        self.tear_method()

    def test_no_proxy_returns_none(self):
        os.environ.pop("PROXY_URL", None)
        os.environ.pop("EXIST_PROXY_URL", None)
        config = get_proxy_config_for_site("exist")
        assert config is None
        self.tear_method()
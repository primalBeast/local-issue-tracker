from __future__ import annotations

from lit.services.split_browser import launchable_http_url, split_rects


def test_launchable_http_url_accepts_http_https():
    assert launchable_http_url("https://jira.example/browse/A-1") == "https://jira.example/browse/A-1"
    assert launchable_http_url("  http://bugs.local/t=1  ") == "http://bugs.local/t=1"


def test_launchable_http_url_rejects_junk():
    assert launchable_http_url("") is None
    assert launchable_http_url("jira.example/A-1") is None
    assert launchable_http_url("javascript:alert(1)") is None
    assert launchable_http_url("file:///c:/secret") is None
    assert launchable_http_url("https://user:pass@evil.example/") is None


def test_split_rects_halves_the_work_area():
    left, right = split_rects((0, 0, 2000, 1000))
    assert left == (0, 0, 1000, 1000)
    assert right == (1000, 0, 1000, 1000)

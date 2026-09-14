"""Tests for the home-screen app: manifest, icons and service worker.

These exist because the install and update path is easy to break silently. A
missing icon size or an unsubstituted version string still "works" in a desktop
browser but leaves the phone with a stale app or a blank shortcut.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from mealplanner.build import build

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
REQUIRED_ICONS = {"icon-192.png": 192, "icon-512.png": 512, "apple-touch-icon.png": 180}


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    return build(tmp_path_factory.mktemp("site"))


def test_icons_exist_at_the_declared_sizes():
    for name, size in REQUIRED_ICONS.items():
        path = ASSETS / name
        assert path.exists(), f"{name} missing; run scripts/mkicons.py"
        assert png_size(path) == (size, size), f"{name} is not {size}x{size}"


def test_manifest_is_valid_and_installable(site):
    manifest = json.loads((site / "manifest.webmanifest").read_text(encoding="utf-8"))

    assert manifest["name"] and manifest["short_name"]
    assert manifest["display"] == "standalone", "must open without browser chrome"
    # Relative so the app works under the /meal-planner/ project path.
    assert not manifest["start_url"].startswith("/")
    assert not manifest["scope"].startswith("/")

    sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes, "Android needs 192 and 512 to offer install"
    purposes = {icon.get("purpose") for icon in manifest["icons"]}
    assert "maskable" in purposes, "without a maskable icon Android adds a white border"

    for icon in manifest["icons"]:
        assert (site / icon["src"]).exists(), f"manifest references missing {icon['src']}"


def test_service_worker_is_versioned(site):
    sw = (site / "sw.js").read_text(encoding="utf-8")
    assert "__VERSION__" not in sw, "version placeholder was not substituted"
    assert 'VERSION = "' in sw
    version = sw.split('VERSION = "')[1].split('"')[0]
    assert len(version) == 12 and version.isalnum()


def test_version_changes_when_the_page_changes(tmp_path, monkeypatch):
    """A deploy must retire the old cache, or phones keep the stale app."""
    import mealplanner.build as b

    first = (build(tmp_path / "a") / "sw.js").read_text(encoding="utf-8")

    original = b.payload
    monkeypatch.setattr(b, "payload", lambda: {**original(), "targets": {"kcal": 1, "protein": 1}})
    second = (build(tmp_path / "b") / "sw.js").read_text(encoding="utf-8")

    assert first != second, "changing the page did not change the service worker version"


def test_version_is_reproducible(tmp_path):
    """Two builds of the same content must agree, or every deploy wipes the cache."""
    a = (build(tmp_path / "a") / "sw.js").read_text(encoding="utf-8")
    b = (build(tmp_path / "b") / "sw.js").read_text(encoding="utf-8")
    assert a == b


def test_service_worker_does_not_cache_arbitrary_urls(site):
    sw = (site / "sw.js").read_text(encoding="utf-8")
    assert "CACHEABLE" in sw, "the worker must restrict what it stores"
    assert "request.method" in sw, "non-GET requests must be left alone"


def test_page_is_wired_up_for_installation(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' in html
    assert "apple-touch-icon" in html
    assert 'name="theme-color"' in html
    assert "serviceWorker" in html and 'register("sw.js")' in html
    # Registering from a file:// copy throws; the app must not depend on it.
    assert "location.protocol.startsWith" in html


def test_everything_the_page_references_is_published(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    for name in ("manifest.webmanifest", "apple-touch-icon.png", "icon-192.png", "sw.js"):
        assert name in html, f"{name} is not referenced by the page"
        assert (site / name).exists(), f"{name} referenced but not written to the site"

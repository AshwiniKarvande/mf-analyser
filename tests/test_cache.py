"""Tests for cache layer."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import pytest

from mf_analyser.config import NAV_CACHE_DIR
from mf_analyser.data.cache import _is_stale, clear_nav_cache, list_cached_navs


# ─── _is_stale ────────────────────────────────────────────────────────────────

def test_is_stale_missing_file(tmp_path):
    missing = tmp_path / "nonexistent.csv"
    assert _is_stale(missing, ttl_hours=24) is True


def test_is_stale_fresh_file(tmp_path):
    fresh = tmp_path / "fresh.csv"
    fresh.write_text("test")
    assert _is_stale(fresh, ttl_hours=24) is False


def test_is_stale_old_file(tmp_path):
    old = tmp_path / "old.csv"
    old.write_text("test")
    # Set mtime to 2 days ago
    old_time = time.time() - 48 * 3600
    import os
    os.utime(old, (old_time, old_time))
    assert _is_stale(old, ttl_hours=24) is True


# ─── list_cached_navs ─────────────────────────────────────────────────────────

def test_list_cached_navs_empty(monkeypatch, tmp_path):
    monkeypatch.setattr("mf_analyser.data.cache.NAV_CACHE_DIR", tmp_path / "nav")
    result = list_cached_navs()
    assert result == []


def test_list_cached_navs_populated(monkeypatch, tmp_path):
    nav_dir = tmp_path / "nav"
    nav_dir.mkdir()
    (nav_dir / "118989.csv").write_text("date,nav\n2024-01-01,100.0")
    (nav_dir / "122639.csv").write_text("date,nav\n2024-01-01,200.0")
    monkeypatch.setattr("mf_analyser.data.cache.NAV_CACHE_DIR", nav_dir)
    result = list_cached_navs()
    assert set(result) == {"118989", "122639"}


# ─── clear_nav_cache ─────────────────────────────────────────────────────────

def test_clear_nav_cache(monkeypatch, tmp_path):
    nav_dir = tmp_path / "nav"
    nav_dir.mkdir()
    csv = nav_dir / "999999.csv"
    csv.write_text("date,nav\n2024-01-01,50.0")
    monkeypatch.setattr("mf_analyser.data.cache.NAV_CACHE_DIR", nav_dir)
    clear_nav_cache("999999")
    assert not csv.exists()

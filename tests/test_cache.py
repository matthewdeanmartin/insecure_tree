"""Tests for the SQLite cache."""

import time

import pytest

from insecure_tree.cache import Cache


@pytest.fixture
def cache(tmp_path):
    return Cache(path=tmp_path / "test.db")


def test_miss_returns_none(cache):
    assert cache.get("test", "nonexistent") is None


def test_put_and_get(cache):
    cache.put("test", "k1", "hello", ttl_seconds=60)
    assert cache.get("test", "k1") == "hello"


def test_expired_returns_none(cache):
    cache.put("test", "k2", "soon-expired", ttl_seconds=0)
    time.sleep(0.01)
    assert cache.get("test", "k2") is None


def test_put_json_and_get_json(cache):
    obj = {"a": 1, "b": [1, 2, 3]}
    cache.put_json("meta", "pkg==1.0", obj, ttl_seconds=60)
    result = cache.get_json("meta", "pkg==1.0")
    assert result == obj


def test_clean(cache):
    cache.put("test", "alive", "v", ttl_seconds=3600)
    cache.put("test", "dead", "v", ttl_seconds=0)
    time.sleep(0.01)
    n = cache.clean()
    assert n == 1
    assert cache.get("test", "alive") == "v"
    assert cache.get("test", "dead") is None


def test_different_domains_isolated(cache):
    cache.put("domain_a", "k", "val_a", 60)
    cache.put("domain_b", "k", "val_b", 60)
    assert cache.get("domain_a", "k") == "val_a"
    assert cache.get("domain_b", "k") == "val_b"

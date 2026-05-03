"""Tests for name normalization."""

from insecure_tree.normalize import canonicalize, parse_version


def test_canonicalize_basic():
    assert canonicalize("Requests") == "requests"
    assert canonicalize("Pillow") == "pillow"
    assert canonicalize("beautifulsoup4") == "beautifulsoup4"


def test_canonicalize_dashes_underscores():
    assert canonicalize("My-Package") == "my-package"
    assert canonicalize("my_package") == "my-package"
    assert canonicalize("My.Package") == "my-package"


def test_parse_version():
    v = parse_version("2.32.3")
    assert v.major == 2
    assert v.minor == 32

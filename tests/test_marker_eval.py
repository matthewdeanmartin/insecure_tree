"""Tests for marker evaluation."""

from insecure_tree.marker_eval import evaluate_marker


def test_empty_marker_is_true():
    assert evaluate_marker("") is True


def test_always_false_marker():
    assert evaluate_marker('python_version == "99.0"') is False


def test_always_true_marker():
    assert evaluate_marker('python_version >= "2.7"') is True

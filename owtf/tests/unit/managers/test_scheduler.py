"""
tests.unit.managers.test_scheduler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the adaptive priority scheduler.
"""

import pytest
from owtf.managers.scheduler import (
    compute_score,
    boost_related_work,
    PLUGIN_WEIGHTS,
    TARGET_PRIORITY_BONUS,
    FEEDBACK_BOOST_AMOUNT,
)


# --- Fixtures ---

def make_plugin(plugin_type="active"):
    return {"type": plugin_type, "key": f"{plugin_type}@OWTF-TEST-001", "group": "web"}


def make_target(user_priority=2):
    return {"user_priority": user_priority, "target_url": "http://test.com"}


# --- compute_score tests ---

def test_active_plugin_scores_higher_than_passive():
    active = make_plugin("active")
    passive = make_plugin("passive")
    target = make_target()
    assert compute_score(active, target) > compute_score(passive, target)


def test_critical_target_scores_higher_than_low():
    plugin = make_plugin("active")
    critical = make_target(user_priority=1)
    low = make_target(user_priority=4)
    assert compute_score(plugin, critical) > compute_score(plugin, low)


def test_score_is_sum_of_weight_and_bonus():
    plugin = make_plugin("active")   # weight = 4.0
    target = make_target(user_priority=1)  # bonus = 10.0
    assert compute_score(plugin, target) == 14.0


def test_unknown_plugin_type_defaults_to_zero_weight():
    plugin = {"type": "unknown_type", "key": "x@Y", "group": "web"}
    target = make_target(user_priority=4)  # bonus = 0.0
    assert compute_score(plugin, target) == 0.0


def test_missing_plugin_type_defaults_to_passive_weight():
    plugin = {"key": "x@Y", "group": "web"}  # no 'type' key
    target = make_target(user_priority=4)
    # passive weight = 2.0, priority 4 bonus = 0.0
    assert compute_score(plugin, target) == 2.0


def test_missing_user_priority_defaults_to_high_bonus():
    plugin = make_plugin("active")  # weight = 4.0
    target = {"target_url": "http://test.com"}  # no user_priority
    # default user_priority=2 → bonus=5.0
    assert compute_score(plugin, target) == 9.0


def test_all_plugin_types_have_decreasing_scores():
    target = make_target(user_priority=4)  # bonus=0 so score = weight only
    types = ["active", "semi_passive", "passive", "grep", "external"]
    scores = [compute_score(make_plugin(t), target) for t in types]
    assert scores == sorted(scores, reverse=True)
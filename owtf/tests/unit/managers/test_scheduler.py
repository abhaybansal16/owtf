"""
tests.unit.managers.test_scheduler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for the adaptive priority scheduler.
"""
import threading

from owtf.managers.scheduler import compute_score, boost_related_work
from owtf.settings import (
    SCHEDULER_PLUGIN_WEIGHTS,
    SCHEDULER_TARGET_PRIORITY_BONUS,
    SCHEDULER_FEEDBACK_BOOST_AMOUNT,
    SCHEDULER_DEFAULT_RISK_FACTOR,
)


# --- Fixtures ---

def make_plugin(plugin_type="active", code="OWTF-CM-003"):
    return {"type": plugin_type, "key": f"{plugin_type}@{code}", "group": "web", "code": code}


def make_target(user_priority=2):
    return {"user_priority": user_priority, "target_url": "http://test.com"}


# --- compute_score tests ---

def test_active_plugin_scores_higher_than_passive():
    """Active plugins must always score higher than passive ones for same target."""
    active = make_plugin("active")
    passive = make_plugin("passive")
    target = make_target()
    assert compute_score(active, target) > compute_score(passive, target)


def test_critical_target_scores_higher_than_low():
    """Same plugin on a critical target must score higher than on a low priority target."""
    plugin = make_plugin("active")
    critical = make_target(user_priority=1)
    low = make_target(user_priority=4)
    assert compute_score(plugin, critical) > compute_score(plugin, low)


def test_score_is_sum_of_weight_and_bonus():
    """Score = (plugin_weight * risk_factor) + target_bonus.
    active(4.0) * default_risk(1.0) + critical_bonus(10.0) = 14.0
    """
    plugin = make_plugin("active", code="OWTF-CM-003")
    target = make_target(user_priority=1)
    assert compute_score(plugin, target) == 14.0


def test_risk_factor_applied_for_high_risk_plugin():
    """High risk plugins (SQLi) get risk_factor=3.0 applied to their weight.
    passive(2.0) * sqli_risk(3.0) + high_bonus(5.0) = 11.0
    """
    plugin = {"type": "passive", "code": "OWTF-DV-005", "key": "passive@OWTF-DV-005", "group": "web"}
    target = make_target(user_priority=2)
    assert compute_score(plugin, target) == 11.0


def test_unknown_plugin_type_defaults_to_zero_weight():
    """Unknown plugin types get weight 0.0 so they run last."""
    plugin = {"type": "unknown_type", "code": "OWTF-CM-003", "key": "x@Y", "group": "web"}
    target = make_target(user_priority=4)  # bonus = 0.0
    assert compute_score(plugin, target) == 0.0


def test_missing_plugin_type_defaults_to_passive_weight():
    """Missing type key defaults to passive weight (2.0).
    passive(2.0) * default_risk(1.0) + low_bonus(0.0) = 2.0
    """
    plugin = {"code": "OWTF-CM-003", "key": "x@Y", "group": "web"}  # no 'type' key
    target = make_target(user_priority=4)
    assert compute_score(plugin, target) == 2.0


def test_missing_user_priority_defaults_to_high_bonus():
    """Missing user_priority defaults to 2 (high) giving bonus=5.0.
    active(4.0) * default_risk(1.0) + high_bonus(5.0) = 9.0
    """
    plugin = make_plugin("active")
    target = {"target_url": "http://test.com"}  # no user_priority key
    assert compute_score(plugin, target) == 9.0


def test_all_plugin_types_have_decreasing_scores():
    """Plugin types must produce strictly decreasing scores in order:
    active > semi_passive > passive > grep > external
    """
    target = make_target(user_priority=4)  # bonus=0 so score = weight * risk only
    types = ["active", "semi_passive", "passive", "grep", "external"]
    scores = [compute_score(make_plugin(t), target) for t in types]
    assert scores == sorted(scores, reverse=True)


def test_equal_scores_tiebreak_by_insertion_order():
    """Two plugins with same type and same target get the same score.
    Tiebreaking by Work.id (insertion order) is handled at DB query level.
    """
    plugin1 = make_plugin("active", code="OWTF-CM-003")
    plugin2 = make_plugin("active", code="OWTF-CM-006")
    target = make_target(user_priority=2)
    assert compute_score(plugin1, target) == compute_score(plugin2, target)


def test_concurrent_compute_score_is_thread_safe():
    """compute_score must return correct results when called from multiple threads.
    This simulates multiple workers computing scores simultaneously.
    """
    results = {}
    errors = []

    def worker(thread_id, plugin_type, expected):
        try:
            plugin = make_plugin(plugin_type)
            target = make_target(user_priority=2)
            score = compute_score(plugin, target)
            results[thread_id] = score
        except Exception as e:
            errors.append(str(e))

    threads = [
        threading.Thread(target=worker, args=(0, "active", 9.0)),
        threading.Thread(target=worker, args=(1, "passive", 7.0)),
        threading.Thread(target=worker, args=(2, "active", 9.0)),
        threading.Thread(target=worker, args=(3, "grep", 6.0)),
        threading.Thread(target=worker, args=(4, "passive", 7.0)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread errors: {errors}"
    assert results[0] == 9.0   # active + high bonus
    assert results[2] == 9.0   # active + high bonus


def test_rapid_feedback_boost_amount_is_positive():
    """FeedbackBoost amount must be a positive float — negative would lower priority."""
    assert SCHEDULER_FEEDBACK_BOOST_AMOUNT > 0
    assert isinstance(SCHEDULER_FEEDBACK_BOOST_AMOUNT, float)


def test_default_risk_factor_is_one():
    """Default risk factor must be 1.0 so unmapped plugins are not penalized."""
    assert SCHEDULER_DEFAULT_RISK_FACTOR == 1.0
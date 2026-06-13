"""
owtf.managers.scheduler
~~~~~~~~~~~~~~~~~~~~~~~

Priority score calculator and feedback boost for the adaptive scheduler.
"""

import logging

from owtf.models.work import Work
from owtf.utils.signals import finding_discovered
from owtf.settings import (
    SCHEDULER_PLUGIN_WEIGHTS,
    SCHEDULER_TARGET_PRIORITY_BONUS,
    SCHEDULER_FEEDBACK_BOOST_AMOUNT,
    SCHEDULER_DEFAULT_RISK_FACTOR,
)

logger = logging.getLogger(__name__)

# Risk factor mapping based on plugin code
# Higher = more critical vulnerability class
RISK_FACTORS = {
    "OWTF-DV-005": 3.0,  # SQL Injection
    "OWTF-DV-012": 3.0,  # Code Injection
    "OWTF-DV-013": 3.0,  # Command Injection
    "OWTF-DV-014": 3.0,  # Buffer Overflow
    "OWTF-DV-001": 2.0,  # Reflected XSS
    "OWTF-DV-002": 2.0,  # Stored XSS
    "OWTF-AZ-001": 2.0,  # Path Traversal
    "OWTF-AZ-002": 2.0,  # Auth Bypass
    "OWTF-AZ-003": 2.0,  # Privilege Escalation
    "OWTF-AT-005": 2.0,  # Bypassing Auth Schema
    "OWTF-ST-001": 2.0,  # Subdomain Takeover
    "OWTF-SM-005": 1.5,  # CSRF
    "OWTF-WGP-001": 1.0, # Clickjacking
    "OWTF-CM-001": 1.0,  # SSL/TLS
}


def compute_score(plugin, target):
    """Compute priority score for a (plugin, target) work item.

    Score formula: (plugin_weight * risk_factor) + target_priority_bonus

    :param plugin: Plugin dict with at least 'type' and 'code' keys
    :type plugin: dict
    :param target: Target dict with at least 'user_priority' key
    :type target: dict
    :return: Priority score — higher means runs first
    :rtype: float
    """
    plugin_weight = SCHEDULER_PLUGIN_WEIGHTS.get(plugin.get("type", "passive"), 0.0)
    risk_factor = RISK_FACTORS.get(plugin.get("code", ""), SCHEDULER_DEFAULT_RISK_FACTOR)
    target_bonus = SCHEDULER_TARGET_PRIORITY_BONUS.get(target.get("user_priority", 2), 5.0)
    score = (plugin_weight * risk_factor) + target_bonus
    logger.debug(
        "Computed score %.1f for plugin '%s' (type=%s, risk=%.1f) on target '%s'",
        score,
        plugin.get("code"),
        plugin.get("type"),
        risk_factor,
        target.get("target_url"),
    )
    return score


def boost_related_work(session, plugin_group, boost_amount=SCHEDULER_FEEDBACK_BOOST_AMOUNT):
    """Boost priority scores of queued work in the same plugin group.

    Called when a high severity finding is discovered so related
    plugins get elevated and run sooner.

    :param session: DB session
    :param plugin_group: Plugin group to boost e.g. 'web', 'network'
    :type plugin_group: str
    :param boost_amount: Amount to add to priority_score
    :type boost_amount: float
    """
    from owtf.models.plugin import Plugin

    updated = (
        session.query(Work)
        .join(Plugin, Work.plugin_key == Plugin.key)
        .filter(Work.active == True, Plugin.group == plugin_group)
        .update(
            {Work.priority_score: Work.priority_score + boost_amount},
            synchronize_session="fetch",
        )
    )
    session.commit()
    logger.info(
        "FeedbackBoost: boosted %d queued tasks in group '%s' by %.1f",
        updated,
        plugin_group,
        boost_amount,
    )


@finding_discovered.connect
def on_finding_discovered(sender, **kwargs):
    """Boost related queued work when a high severity finding is saved."""
    plugin_group = kwargs.get("plugin_group")
    session = kwargs.get("session")
    if plugin_group and session:
        boost_related_work(session, plugin_group)
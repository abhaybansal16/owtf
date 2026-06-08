"""
owtf.managers.scheduler
~~~~~~~~~~~~~~~~~~~~~~~

Priority score calculator and feedback boost for the adaptive scheduler.
"""

import logging

from owtf.models.work import Work
from owtf.utils.signals import finding_discovered

logger = logging.getLogger(__name__)

# Plugin type weights — higher means runs first
PLUGIN_WEIGHTS = {
    "active": 4.0,
    "semi_passive": 3.0,
    "passive": 2.0,
    "grep": 1.0,
    "external": 0.0,
}

# Target priority bonus — user_priority 1=critical, 2=high, 3=medium, 4=low
TARGET_PRIORITY_BONUS = {
    1: 10.0,
    2: 5.0,
    3: 2.0,
    4: 0.0,
}

# How much to boost related tasks when a high severity finding is saved
FEEDBACK_BOOST_AMOUNT = 2.0


def compute_score(plugin, target):
    """Compute priority score for a (plugin, target) work item.

    :param plugin: Plugin dict with at least 'type' key
    :type plugin: dict
    :param target: Target dict with at least 'user_priority' key
    :type target: dict
    :return: Priority score — higher means runs first
    :rtype: float
    """
    plugin_weight = PLUGIN_WEIGHTS.get(plugin.get("type", "passive"), 0.0)
    target_bonus = TARGET_PRIORITY_BONUS.get(target.get("user_priority", 2), 5.0)
    score = plugin_weight + target_bonus
    logger.debug(
        "Computed score %.1f for plugin '%s' on target '%s'",
        score,
        plugin.get("type"),
        target.get("target_url"),
    )
    return score


def boost_related_work(session, plugin_group, boost_amount=FEEDBACK_BOOST_AMOUNT):
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
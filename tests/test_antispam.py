import asyncio

from src.bot.antispam import AntiSpamGuard


def test_antispam_blocks_burst():
    guard = AntiSpamGuard(
        min_interval_seconds=1.0,
        burst_window_seconds=5.0,
        max_actions_in_burst=3,
        notify_interval_seconds=0.0,
    )

    async def scenario():
        decisions = []
        for _ in range(3):
            decisions.append(await guard.register_action(user_id=123))
        return decisions

    decisions = asyncio.run(scenario())
    assert decisions[0].allowed is True
    assert decisions[1].allowed is True
    assert decisions[2].allowed is False
    assert decisions[2].warn_user is True
    assert decisions[2].notify_admin is True


def test_antispam_resets_after_interval():
    guard = AntiSpamGuard(
        min_interval_seconds=0.1,
        burst_window_seconds=1.0,
        max_actions_in_burst=3,
        notify_interval_seconds=0.0,
    )

    async def scenario():
        user_id = 456
        await guard.register_action(user_id)
        await asyncio.sleep(0.2)
        decision = await guard.register_action(user_id)
        return decision

    decision = asyncio.run(scenario())
    assert decision.allowed is True

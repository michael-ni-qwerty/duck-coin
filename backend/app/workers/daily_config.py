"""
Daily config update worker.

Runs once per day to call update_config on the Solana presale program.
This triggers the daily rollover: burns unsold tokens from the previous day,
resets sold_today to 0, advances current_day, and applies the new day's
price / TGE / daily_cap from the hardcoded tokenomics schedule.

The current presale day is computed as:  (today_utc - PRESALE_START_DATE).days + 1
so that PRESALE_START_DATE itself is Day 1.
"""

import asyncio
import logging
from datetime import datetime, time, timezone, timedelta

from app.services.solana import solana_service
from app.workers.tokenomics import SCHEDULE, TOTAL_DAYS, _get_presale_day

logger = logging.getLogger(__name__)

# Run at 00:05 UTC each day (small offset to ensure the on-chain day has rolled)
DAILY_RUN_TIME = time(0, 5, tzinfo=timezone.utc)


def _seconds_until(target: time) -> float:
    """Return seconds from now until the next occurrence of `target` (UTC)."""
    now = datetime.now(timezone.utc)
    target_dt = datetime.combine(now.date(), target)
    if target_dt <= now:
        target_dt += timedelta(days=1)
    return (target_dt - now).total_seconds()


async def _do_daily_update() -> bool:
    day = _get_presale_day()
    logger.info(f"daily_config: presale day {day}")

    if day < 1:
        logger.info("daily_config: presale has not started yet, skipping")
        return True

    try:
        config_data = await solana_service.get_config_data()
    except Exception as e:
        logger.error(f"daily_config: failed to fetch config: {e}")
        return False

    if not config_data:
        logger.warning("daily_config: no on-chain config found, skipping")
        return True

    if day > TOTAL_DAYS + 1:
        logger.info(
            f"daily_config: presale already ended on day {TOTAL_DAYS}, skipping"
        )
        return True

    if day == TOTAL_DAYS + 1:
        new_price = 0
        new_tge = 0
        new_daily_cap = 0

        if config_data["daily_cap"] == 0:
            logger.info("daily_config: presale already ended on-chain, skipping")
            return True

        logger.info(
            f"daily_config: presale schedule ended (day {day} == {TOTAL_DAYS} + 1), "
            "sending zeroes to close out config"
        )
    else:
        day_cfg = SCHEDULE[day]
        new_price = day_cfg.price_usd
        new_tge = day_cfg.tge
        new_daily_cap = day_cfg.daily_cap
        if config_data["token_price_usd"] >= day_cfg.price_usd:
            logger.info(
                "daily_config: on-chain price is already >= today's price, skipping"
            )
            return True
        logger.info(
            f"daily_config: day {day} → price={day_cfg.price_usd}, "
            f"tge={day_cfg.tge}, daily_cap={new_daily_cap}"
        )

    try:
        tx_sig = await solana_service.update_config(
            new_price=new_price,
            new_tge=new_tge,
            new_daily_cap=new_daily_cap,
        )
        logger.info(f"daily_config: rollover complete, tx={tx_sig}")
        return True
    except Exception as e:
        logger.error(f"daily_config: update_config failed: {e}")
        return False


async def daily_config_loop() -> None:
    """Background loop that fires _do_daily_update once per day."""
    # Run once on startup to catch up if we missed the window or just deployed
    logger.info("daily_config: checking if rollover needed on startup...")
    await _do_daily_update()

    # Now enter the regular daily schedule
    while True:
        wait = _seconds_until(DAILY_RUN_TIME)
        logger.info(f"daily_config: next scheduled run in {wait:.0f}s")
        await asyncio.sleep(wait)

        while True:
            logger.info("daily_config: starting daily rollover")
            try:
                success = await _do_daily_update()
            except Exception as e:
                logger.error(f"daily_config: unhandled error: {e}")
                success = False

            if success:
                break

            logger.info("daily_config: update failed, retrying in 5 minutes")
            await asyncio.sleep(300)

        # Sleep a bit to avoid double-firing on the same second
        await asyncio.sleep(60)

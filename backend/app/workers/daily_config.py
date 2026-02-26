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
from datetime import date, datetime, time, timezone, timedelta

from app.core.config import settings
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


async def _do_daily_update() -> None:
    """Look up today's schedule entry and call update_config on-chain."""
    if not settings.presale_start_date:
        logger.warning("daily_config: PRESALE_START_DATE not set, skipping")
        return

    day = _get_presale_day()
    logger.info(f"daily_config: presale day {day}")

    if day < 1:
        logger.info("daily_config: presale has not started yet, skipping")
        return

    if day > TOTAL_DAYS:
        logger.info(
            f"daily_config: presale schedule ended (day {day} > {TOTAL_DAYS}), "
            "sending daily_cap=0 to end presale"
        )
        # Past the last day — send daily_cap=0 which sets status to PresaleEnded
        last = SCHEDULE[TOTAL_DAYS]
        try:
            tx_sig = await solana_service.update_config(
                new_price=last.price_usd,
                new_tge=last.tge,
                new_daily_cap=0,
            )
            logger.info(f"daily_config: presale ended, tx={tx_sig}")
        except Exception as e:
            logger.error(f"daily_config: end-presale update_config failed: {e}")
        return

    day_cfg = SCHEDULE[day]
    logger.info(
        f"daily_config: day {day} → price={day_cfg.price_usd}, "
        f"tge={day_cfg.tge}, daily_cap={day_cfg.daily_cap}"
    )

    try:
        tx_sig = await solana_service.update_config(
            new_price=day_cfg.price_usd,
            new_tge=day_cfg.tge,
            new_daily_cap=day_cfg.daily_cap,
        )
        logger.info(f"daily_config: rollover complete, tx={tx_sig}")
    except Exception as e:
        logger.error(f"daily_config: update_config failed: {e}")


async def daily_config_loop() -> None:
    """Background loop that fires _do_daily_update once per day."""
    while True:
        wait = _seconds_until(DAILY_RUN_TIME)
        logger.info(f"daily_config: next run in {wait:.0f}s")
        await asyncio.sleep(wait)

        logger.info("daily_config: starting daily rollover")
        try:
            await _do_daily_update()
        except Exception as e:
            logger.error(f"daily_config: unhandled error: {e}")

        # Sleep a bit to avoid double-firing on the same second
        await asyncio.sleep(60)


""

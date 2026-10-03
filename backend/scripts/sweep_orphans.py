"""Look for objects in the media bucket that nothing points at -- and, with
--apply, do what the nightly job does about them.

    python -m scripts.sweep_orphans                 # report only, writes nothing
    python -m scripts.sweep_orphans --apply         # mark new orphans, delete expired
    python -m scripts.sweep_orphans --apply --force # past a halted night

Runs the same `sweep` as the 04:00 Celery task (`app/services/orphans.py`
says what counts as claimed and why nothing is deleted on first sight). A dry
run lists what would be marked and what would be deleted tonight.

`--force` is for the night the valve stopped -- most of one family looked
abandoned at once -- after reading the report and knowing why (a `--purge`
of demo data, say). `--quarantine-days` shortens the wait for a drill on a
development bucket; on a server whose database is backed up, leave it alone.
"""

import argparse
import asyncio
from datetime import timedelta

from app.core.db import SessionLocal
from app.services.orphans import QUARANTINE, sweep
from app.services.storage import build_storage

SHOWN = 20


async def main(apply: bool, force: bool, quarantine: timedelta) -> None:
    storage = build_storage()
    async with SessionLocal() as session:
        report = await sweep(session, storage, apply=apply, force=force, quarantine=quarantine)

    for line in report.lines():
        print(line)
    for title, objects in (("marked", report.marked), ("deleted", report.deleted)):
        if objects:
            verb = title if report.applied else f"would be {title}"
            print(f"\n{verb}:")
            for obj in objects[:SHOWN]:
                print(f"  {obj.key}  ({obj.size} B, {obj.last_modified:%Y-%m-%d})")
            if len(objects) > SHOWN:
                print(f"  ... and {len(objects) - SHOWN} more")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write marks and delete")
    parser.add_argument("--force", action="store_true", help="go past the valve")
    parser.add_argument(
        "--quarantine-days",
        type=float,
        default=QUARANTINE.days,
        help=f"days a mark waits before deletion (default {QUARANTINE.days})",
    )
    args = parser.parse_args()
    asyncio.run(main(args.apply, args.force, timedelta(days=args.quarantine_days)))

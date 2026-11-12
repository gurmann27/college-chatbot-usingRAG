"""Azure Function Blob / Event Grid trigger for continuous knowledge-base ingestion."""
from __future__ import annotations

import asyncio
import logging

from scripts.ingest import run_cli

log = logging.getLogger(__name__)


def main(blob_event: object) -> dict:
    """Entry point invoked by Azure Functions runtime when a blob changes in `college-docs`."""
    name = getattr(blob_event, "name", "") or ""
    if "/" in name and name.startswith("college-docs/"):
        name = name.split("college-docs/", 1)[1]
    log.info("blob_trigger_invoked", extra={"blob_name": name})
    return asyncio.run(run_cli(blob=name or None, force=False))


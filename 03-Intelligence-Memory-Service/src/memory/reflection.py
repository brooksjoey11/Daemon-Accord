from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import structlog

from .models import IncidentLog, SiteAdapter
from .repo import MemoryRepository

logger = structlog.get_logger(__name__)


class Reflector:
    """
    Consumes incident logs and updates site adapters to self-heal selectors/waits.
    """

    def __init__(self, repo: MemoryRepository) -> None:
        self.repo = repo

    async def reflect_domain(self, domain: str) -> Optional[SiteAdapter]:
        incidents = await self.repo.fetch_incidents(domain)
        if not incidents:
            return await self.repo.get_adapter(domain)

        adapter = await self.repo.get_adapter(domain)
        if adapter is None:
            adapter = SiteAdapter(domain=domain, selectors={}, wait_strategies={}, version=1)

        updated = self._apply_rules(adapter, incidents)
        updated.updated_at = datetime.utcnow()

        audit_entry = {
            "timestamp": updated.updated_at.isoformat(),
            "applied_rules": [i.error_type for i in incidents],
            "version": updated.version,
        }
        updated.audit_trail.append(audit_entry)

        adapter = await self.repo.save_adapter(updated)
        logger.info(
            "adapter_reflected",
            domain=domain,
            version=adapter.version,
            applied_rules=audit_entry["applied_rules"],
        )
        return adapter

    def _apply_rules(self, adapter: SiteAdapter, incidents: List[IncidentLog]) -> SiteAdapter:
        """
        Simple rule engine:
        - selector_miss -> add fallback selector strategy and bump version
        - timeout -> add wait_for network_idle/longer timeout
        """
        selectors = dict(adapter.selectors)
        wait_strategies: Dict[str, object] = dict(adapter.wait_strategies)
        bumped = False

        for incident in incidents:
            if incident.error_type == "selector_miss":
                selectors.setdefault("fallback", "//body//*")
                selectors.setdefault("text", "//*[text()]")
                bumped = True
            if incident.error_type == "timeout":
                wait_strategies["network_idle"] = True
                wait_strategies["timeout_ms"] = max(
                    30000, int(wait_strategies.get("timeout_ms", 15000))
                )
                bumped = True
            if incident.error_type == "blocked":
                wait_strategies["stealth"] = True
                bumped = True

        if bumped:
            adapter.version += 1
            adapter.selectors = selectors
            adapter.wait_strategies = wait_strategies

        return adapter

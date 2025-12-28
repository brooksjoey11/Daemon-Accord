"""
Compliance and Policy Models

Defines data models for policy controls and audit logging.
"""
from sqlmodel import SQLModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum as PyEnum


class AuthorizationMode(str, PyEnum):
    """Authorization mode for job execution."""
    PUBLIC = "public"  # Public pages, no restrictions
    CUSTOMER_AUTHORIZED = "customer-authorized"  # Customer has authorization
    INTERNAL = "internal"  # Internal use only


class PolicyAction(str, PyEnum):
    """Policy enforcement actions."""
    ALLOW = "allow"
    DENY = "deny"
    RATE_LIMIT = "rate_limit"
    CONCURRENCY_LIMIT = "concurrency_limit"
    STRATEGY_RESTRICTED = "strategy_restricted"


class DomainPolicy(SQLModel, table=True):
    """
    Domain-level policy configuration.
    
    Controls access, rate limits, and concurrency for specific domains.
    """
    __tablename__ = "domain_policies"
    
    id: str = Field(primary_key=True, description="Policy ID")
    domain: str = Field(index=True, unique=True, description="Target domain (e.g., 'example.com')")
    
    # Access control
    allowed: bool = Field(default=True, description="Domain is allowed (allowlist mode)")
    denied: bool = Field(default=False, description="Domain is denied (denylist mode)")
    
    # Rate limiting
    rate_limit_per_minute: Optional[int] = Field(default=None, description="Max requests per minute")
    rate_limit_per_hour: Optional[int] = Field(default=None, description="Max requests per hour")
    
    # Concurrency
    max_concurrent_jobs: Optional[int] = Field(default=None, description="Max concurrent jobs for this domain")
    
    # Strategy restrictions (based on authorization)
    allowed_strategies: Optional[str] = Field(
        default=None,
        description="Comma-separated list of allowed strategies (e.g., 'vanilla,stealth,assault')"
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = Field(default=None, description="Policy notes")
    
    def get_allowed_strategies_list(self) -> List[str]:
        """Get list of allowed strategies."""
        if not self.allowed_strategies:
            return ["vanilla"]  # Default to vanilla only
        return [s.strip() for s in self.allowed_strategies.split(",")]
    
    def is_strategy_allowed(self, strategy: str) -> bool:
        """Check if strategy is allowed for this domain."""
        allowed = self.get_allowed_strategies_list()
        return strategy.lower() in [s.lower() for s in allowed]


class AuditLog(SQLModel, table=True):
    """
    Audit log for policy decisions and enforcement actions.
    
    Records all policy checks and enforcement actions for compliance.
    """
    __tablename__ = "audit_logs"
    
    id: str = Field(primary_key=True, description="Audit log ID")
    job_id: str = Field(index=True, description="Job ID this log entry relates to")
    domain: str = Field(index=True, description="Target domain")
    
    # Policy check
    policy_id: Optional[str] = Field(default=None, description="Domain policy ID if applicable")
    authorization_mode: AuthorizationMode = Field(description="Authorization mode for this job")
    strategy: str = Field(description="Execution strategy requested")
    
    # Decision
    action: PolicyAction = Field(description="Policy action taken")
    allowed: bool = Field(description="Whether job was allowed")
    reason: Optional[str] = Field(default=None, description="Reason for decision")
    
    # Enforcement details
    rate_limit_applied: bool = Field(default=False, description="Rate limit was applied")
    concurrency_limit_applied: bool = Field(default=False, description="Concurrency limit was applied")
    strategy_restricted: bool = Field(default=False, description="Strategy was restricted")
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    user_id: Optional[str] = Field(default=None, description="User/API key that created job")
    ip_address: Optional[str] = Field(default=None, description="IP address of request")
    
    # Additional context
    context: Optional[str] = Field(
        default=None,
        description="JSON-encoded additional context (rate limit counts, concurrency counts, etc.)"
    )


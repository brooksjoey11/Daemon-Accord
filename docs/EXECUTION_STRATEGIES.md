# Execution Strategies

**Overview of available execution strategies and their positioning.**

---

## Production Core Strategies

These strategies are **production-ready** and available to all subscription tiers:

### Vanilla Executor

**Tier:** Starter, Professional, Enterprise  
**Status:** Production-ready  
**Use Case:** Standard web automation, public pages, low-risk targets

**Features:**
- Standard browser automation
- No evasion techniques
- Fast execution
- Suitable for public content

**When to Use:**
- Public pages with no protection
- Documentation sites
- Public APIs
- Low-risk targets

---

### Stealth Executor

**Tier:** Professional, Enterprise  
**Status:** Production-ready  
**Use Case:** Protected sites requiring basic evasion

**Features:**
- Basic evasion techniques
- Fingerprint randomization
- Framework detection evasion
- Protocol-level evasion
- Memory artifact hiding

**When to Use:**
- Sites with basic bot protection
- Customer-authorized access
- Moderate protection levels

---

### Assault Executor

**Tier:** Enterprise  
**Status:** Production-ready  
**Use Case:** Highly protected sites requiring maximum evasion

**Features:**
- Maximum evasion capabilities
- Advanced fingerprint randomization
- Enhanced protocol evasion
- Comprehensive artifact hiding
- Aggressive timing obfuscation

**When to Use:**
- Highly protected sites
- Enterprise internal use
- Maximum evasion requirements

---

## Enterprise Advanced Features

These strategies are **enterprise features** available to Enterprise tier customers:

### Ultimate Stealth Executor

**Tier:** Enterprise only  
**Status:** Enterprise advanced feature  
**Use Case:** Maximum stealth for highly protected sites

**Features:**
- All Stealth + Assault capabilities
- Human behavior simulation
- Advanced timing obfuscation
- Network request obfuscation
- Complete artifact cleanup
- Multi-phase evasion

**When to Use:**
- Maximum stealth requirements
- Highly sophisticated protection
- Enterprise internal use cases
- Specialized evasion needs

**Access:** Requires `authorization_mode=internal` (Enterprise tier)

---

### Custom Executor

**Tier:** Enterprise only  
**Status:** Enterprise advanced feature  
**Use Case:** Custom execution logic and specialized evasion techniques

**Features:**
- Extends Stealth Executor
- Custom JavaScript injection
- Custom header rotation
- User agent rotation
- Custom evasion techniques
- Configurable behavior

**When to Use:**
- Custom execution requirements
- Specialized evasion techniques
- Unique use cases
- Enterprise internal development

**Access:** Requires `authorization_mode=internal` (Enterprise tier)

---

## Strategy Selection

### By Authorization Mode

**Public Mode:**
- ✅ Vanilla only

**Customer-Authorized Mode:**
- ✅ Vanilla
- ✅ Stealth

**Internal Mode (Enterprise):**
- ✅ Vanilla
- ✅ Stealth
- ✅ Assault
- ✅ Ultimate Stealth (Enterprise Advanced)
- ✅ Custom Executor (Enterprise Advanced)

### By Domain Policy

Domain policies can restrict which strategies are allowed for specific domains:

```python
domain_policy = DomainPolicy(
    domain="example.com",
    allowed_strategies="vanilla,stealth"  # Assault not allowed
)
```

---

## Validation

### Production Core Strategies

**Validated:**
- ✅ Unit tests
- ✅ Integration tests
- ✅ E2E validation
- ✅ Proof pack validation
- ✅ Production deployment

**Evidence:**
- Test suite: `01-Core-Execution-Engine/tests/test_strategies.py`
- Proof pack: Tests vanilla, stealth, assault executors
- Production use: Deployed and operational

### Enterprise Advanced Features

**Validated:**
- ✅ Unit tests (smoke tests)
- ✅ Instantiation tests
- ✅ Method existence tests
- ✅ Execution smoke tests

**Evidence:**
- Test suite: `01-Core-Execution-Engine/tests/test_advanced_executors.py`
- Code: Fixed and operational
- Positioning: Enterprise tier only

**Note:** Enterprise advanced features are functional and tested, but positioned as enterprise features for specialized use cases rather than general production use.

---

## Best Practices

### Strategy Selection

1. **Start with Vanilla:** Use for public pages, no protection
2. **Upgrade to Stealth:** If basic protection detected
3. **Use Assault:** For highly protected sites (Enterprise)
4. **Consider Ultimate/Custom:** For specialized enterprise needs

### Authorization

- **Public pages:** Use public mode with vanilla
- **Customer-authorized:** Use customer-authorized mode with stealth
- **Enterprise use:** Use internal mode with any strategy

### Policy Compliance

- All strategies subject to domain policies
- Rate limits apply to all strategies
- Concurrency limits apply to all strategies
- Audit logging for all strategies

---

## Summary

**Production Core (All Tiers):**
- Vanilla ✅ Production-ready
- Stealth ✅ Production-ready
- Assault ✅ Production-ready

**Enterprise Advanced (Enterprise Tier):**
- Ultimate Stealth ✅ Enterprise feature
- Custom Executor ✅ Enterprise feature

**All strategies:**
- Subject to policy controls
- Fully audited
- Tested and validated

---

**Last Updated:** 2024-01-01  
**Version:** 1.0.0


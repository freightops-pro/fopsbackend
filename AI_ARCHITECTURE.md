# FreightOps AI Agent Architecture

**Production-Ready Autonomous TMS System**
Last Updated: December 15, 2025

---

## Executive Summary

FreightOps implements a **5-agent AI workforce** coordinated by an **Agent Orchestrator** (the "supervisor") that manages multi-agent collaboration, enforces compliance checks, and provides real-time visibility into AI decision-making through the **Glass Door Stream** system.

**Key Characteristics:**
- ✅ **Fully Autonomous** - Agents make final decisions with minimal human intervention
- ✅ **Production Ready** - Real database operations, no placeholders or mock functions
- ✅ **Self-Correcting** - Agents audit each other before execution
- ✅ **Full Transparency** - Real-time WebSocket stream of AI thinking and decisions
- ✅ **Cost-Optimized** - Llama 4 Scout (cheap/fast) + Maverick (expensive/smart) routing

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GLASS DOOR UI                            │
│   Real-time WebSocket Stream of Agent Thoughts/Actions      │
│   (Investor-facing transparency dashboard)                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 AGENT ORCHESTRATOR                          │
│  (The "Supervisor" - Workflow Coordinator)                  │
│                                                             │
│  Responsibilities:                                          │
│  - Manages multi-agent collaboration loops                 │
│  - Enforces compliance checks and approval gates           │
│  - Streams real-time events to Glass Door UI               │
│  - Handles retries and error recovery                      │
│  - Maintains audit trail of all decisions                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┴────────────────────┐
        ↓                   ↓                     ↓
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   ANNIE AI    │  │    ADAM AI    │  │   ATLAS AI    │
│  (Dispatch)   │  │ (Compliance)  │  │  (Finance)    │
│               │  │               │  │               │
│ Scout 17B     │  │ Maverick 400B │  │ Maverick 400B │
│ Fast/Cheap    │  │ Deep Audit    │  │ Precision Math│
└───────────────┘  └───────────────┘  └───────────────┘
        ↓                   ↓                     ↓
┌───────────────┐  ┌───────────────┐
│ FLEET MGR AI  │  │  HARPER AI    │
│  (Fleet Ops)  │  │ (HR/Payroll)  │
│               │  │               │
│ Maverick 400B │  │ Maverick 400B │
│ Fleet Safety  │  │ Payroll Math  │
└───────────────┘  └───────────────┘
        ↓
┌─────────────────────────────────────────────────────────────┐
│              DATABASE (PostgreSQL via NeonDB)               │
│  - Production database for autonomous execution             │
│  - Branch database for safe SQL testing (future)           │
└─────────────────────────────────────────────────────────────┘
```

---

## The Five AI Agents

### 1. Annie AI - AI Dispatcher
**Role:** Operations coordinator and load dispatcher
**Model:** Llama 4 Scout 17B (10M token context, vision-enabled)
**Why Scout:** High-volume operations, needs to remember entire conversation history, processes PDFs

**Capabilities:**
- Load assignment to optimal drivers
- Driver-load matching based on equipment, location, preferences
- PDF rate confirmation processing (vision)
- Pickup/delivery coordination
- 10M token context = remembers 6 months of conversations

**Capacity:** 500+ loads/month
**Cost:** $0.10 per 1M tokens (ultra-cheap for high volume)

**Production Tools:**
- `find_best_driver_for_load()` - Semantic driver matching with vector embeddings
- `create_load()` - Full load creation with BOL validation
- `assign_driver_to_load()` - Database execution of assignment

---

### 2. Adam AI - Safety & Compliance Officer
**Role:** DOT compliance auditor and safety gatekeeper
**Model:** Llama 4 Maverick 400B (MoE, deep reasoning)
**Why Maverick:** Safety-critical decisions require expert-level reasoning about HOS regulations

**Capabilities:**
- Hours of Service (HOS) compliance validation
- DOT regulation enforcement
- Database change auditing (prevents unsafe SQL)
- Load assignment compliance verification
- Rejects non-compliant proposals from other agents

**Approval Gates:**
- ❌ Driver HOS insufficient for trip
- ❌ Database change affects >100 rows
- ❌ DELETE query without WHERE clause
- ❌ Any DROP TABLE operations

**Production Tools:**
- `audit_driver_hos()` - HOS validation with 2-hour buffer
- `audit_database_change()` - SQL safety review
- `validate_load_assignment()` - Full compliance check

---

### 3. Atlas AI - CFO Analyst
**Role:** Financial analysis and margin validation
**Model:** Llama 4 Maverick 400B (MoE, precision math)
**Why Maverick:** Requires accurate financial calculations and margin analysis

**Capabilities:**
- Load profitability analysis
- Margin calculation (revenue vs. costs)
- Financial reporting and KPI tracking
- Lane profitability analysis
- Rejects loads below 10-15% margin threshold

**Approval Gates:**
- ⚠️ Load margin < 10% → Flag for human review
- ⚠️ Load margin < 15% → Reject and retry with different driver
- ✅ Load margin ≥ 15% → Autonomous approval

**Production Tools:**
- `calculate_load_margin()` - Revenue, cost, margin analysis
- `analyze_lane_profitability()` - Historical lane performance
- `get_company_financials()` - KPI dashboard data
- `flag_for_approval()` - Human-in-the-loop for low margins

---

### 4. Fleet Manager AI - Fleet Operations Manager
**Role:** Equipment maintenance and fleet health monitoring
**Model:** Llama 4 Maverick 400B (MoE, safety-critical)
**Why Maverick:** Fleet safety decisions require deep reasoning about equipment health

**Capabilities:**
- Predictive maintenance scheduling
- Equipment health monitoring
- Preventive maintenance recommendations
- Downtime impact analysis
- Parts procurement coordination

**Approval Gates:**
- ⏸️ Maintenance cost > $5,000 → Flag for human approval
- ✅ Maintenance cost ≤ $5,000 → Execute autonomously
- 🚨 Critical safety issue → Immediate action (no approval needed)

**Production Tools:**
- `check_equipment_health()` - Health score 0-100
- `schedule_preventive_maintenance()` - Auto-schedule routine service
- `analyze_downtime_impact()` - Calculate revenue loss from downtime
- `flag_for_approval()` - Human review for expensive repairs

---

### 5. Harper AI - HR & Payroll Specialist
**Role:** Payroll processing and HR operations
**Model:** Llama 4 Maverick 400B (MoE, precision calculations)
**Why Maverick:** Payroll math must be 100% accurate (legal/financial liability)

**Capabilities:**
- Driver settlement calculations (mileage, detention, bonuses)
- Weekly/biweekly payroll processing via CheckHQ API
- PTO/sick leave accrual tracking
- Payroll tax calculations (FICA, federal, state)
- Worker's compensation tracking
- Performance-based pay adjustments

**Approval Gates:**
- ⚠️ Payroll discrepancy > $500 → Flag for HR review
- ⚠️ Unusual pay pattern detected → Flag for audit
- ✅ Normal payroll operations → Execute autonomously

**Production Tools:**
- `calculate_driver_settlement()` - Mileage + detention pay
- `process_weekly_payroll()` - Batch payroll for all drivers
- `check_pto_balance()` - PTO accrual and usage
- `calculate_payroll_taxes()` - Tax withholding calculations
- `get_payroll_summary()` - Financial reporting for CFO
- `flag_payroll_issue()` - Human approval for discrepancies

**Integration:** CheckHQ API for payroll submission (not Gusto)

---

## The Agent Orchestrator (The "Supervisor")

**Location:** `app/services/agent_orchestrator.py`

The Orchestrator is **not a conversational AI agent** - it's a **workflow coordinator** that manages multi-agent collaboration. Think of it as the "CEO" who delegates tasks and ensures quality control.

### Orchestrator Responsibilities

1. **Workflow Management**
   - Routes tasks to appropriate agents
   - Manages multi-agent collaboration loops
   - Handles retries and error recovery
   - Maintains execution state

2. **Quality Control**
   - Enforces compliance checks (Adam audits)
   - Validates profitability (Atlas checks)
   - Prevents unsafe operations
   - Logs all decisions for audit trail

3. **Real-Time Visibility**
   - Broadcasts events to Glass Door Stream
   - Logs agent thinking, decisions, rejections
   - Provides investor-facing transparency
   - Creates WebSocket events for frontend

4. **Approval Gates**
   - Autonomous execution for safe operations
   - Human approval for high-risk/high-cost actions
   - Retry logic for rejected proposals

### Orchestrator Workflows

#### 1. Load Assignment Workflow (Fully Autonomous)

```
┌─────────────────────────────────────────────────┐
│ ORCHESTRATOR: execute_load_assignment_workflow  │
└─────────────────────────────────────────────────┘
                    ↓
    ┌───────────────────────────────┐
    │ STEP 1: Annie Proposes Driver │
    │ - Find best match by location │
    │ - Consider equipment type     │
    │ - Check availability (HOS)    │
    └───────────────┬───────────────┘
                    ↓
    ┌───────────────────────────────┐
    │ STEP 2: Adam Audits Proposal  │
    │ - Validate HOS compliance     │
    │ - Check DOT regulations       │
    │ - REJECT if non-compliant     │
    └───────────────┬───────────────┘
                    ↓
            ┌───────┴───────┐
            │  Compliant?   │
            └───────┬───────┘
                    │
        ┌───────────┴───────────┐
        │ NO                YES │
        ↓                       ↓
    ┌───────┐          ┌────────────────┐
    │ Retry │          │ STEP 3: Atlas  │
    │ with  │          │ Checks Margin  │
    │ new   │          └────────┬───────┘
    │driver │                   ↓
    └───┬───┘          ┌────────────────┐
        │              │ Margin ≥ 15%?  │
        │              └────────┬───────┘
        │                       │
        │              ┌────────┴────────┐
        │              │ NO          YES │
        │              ↓                 ↓
        │          ┌───────┐      ┌──────────┐
        └──────────│ Retry │      │ EXECUTE  │
                   │ with  │      │ Database │
                   │cheaper│      │ UPDATE   │
                   │driver │      └──────────┘
                   └───────┘
```

**Characteristics:**
- **Fully autonomous** - No human approval required
- **Self-correcting** - Retries up to 3 times if rejected
- **Multi-agent checks** - Adam (compliance) + Atlas (finance)
- **Glass Door visible** - Every decision streamed to UI

**Code:** Lines 42-250 in `agent_orchestrator.py`

---

#### 2. Maintenance Workflow (Conditional Approval)

```
┌──────────────────────────────────────────┐
│ ORCHESTRATOR: execute_maintenance_workflow│
└──────────────────────────────────────────┘
                    ↓
    ┌───────────────────────────────────┐
    │ STEP 1: Fleet Manager Diagnoses   │
    │ - Check equipment health (0-100)  │
    │ - Identify maintenance needs      │
    └───────────────┬───────────────────┘
                    ↓
    ┌───────────────────────────────────┐
    │ Health Score < 90?                │
    └───────────────┬───────────────────┘
                    │
            ┌───────┴────────┐
            │ NO         YES │
            ↓                ↓
    ┌───────────┐   ┌────────────────┐
    │ No Action │   │ STEP 2: Estimate│
    │  Needed   │   │ Cost & Schedule │
    └───────────┘   └────────┬───────┘
                             ↓
                    ┌────────────────┐
                    │ Cost > $5,000? │
                    └────────┬───────┘
                             │
                    ┌────────┴────────┐
                    │ YES         NO  │
                    ↓                 ↓
            ┌────────────┐    ┌──────────────┐
            │ FLAG FOR   │    │ AUTONOMOUS   │
            │ HUMAN      │    │ EXECUTION    │
            │ APPROVAL   │    │ (Auto-schedule│
            └────────────┘    │ maintenance) │
                              └──────────────┘
```

**Approval Logic:**
- Cost ≤ $5,000: Autonomous execution
- Cost > $5,000: Human approval required
- Critical safety: Immediate action (bypass approval)

**Code:** Lines 330-432 in `agent_orchestrator.py`

---

#### 3. Profitability Workflow (Advisory)

```
┌─────────────────────────────────────────────┐
│ ORCHESTRATOR: execute_load_profitability_workflow │
└─────────────────────────────────────────────┘
                    ↓
    ┌───────────────────────────────────┐
    │ STEP 1: CFO Analyst Calculates   │
    │ - Load revenue (customer rate)   │
    │ - Driver cost estimate           │
    │ - Margin % = (profit/revenue)*100│
    └───────────────┬───────────────────┘
                    ↓
            ┌───────────────┐
            │ Margin ≥ 10%? │
            └───────┬───────┘
                    │
            ┌───────┴────────┐
            │ YES        NO  │
            ↓                ↓
    ┌────────────┐   ┌──────────────┐
    │ APPROVE    │   │ FLAG FOR     │
    │ Load       │   │ REVIEW       │
    │ (Good      │   │ (Recommend   │
    │ margin)    │   │ rejection)   │
    └────────────┘   └──────────────┘
```

**Approval Logic:**
- Margin ≥ 10%: Autonomous approval
- Margin < 10%: Flag for human review with recommendation to reject/renegotiate

**Code:** Lines 434-510 in `agent_orchestrator.py`

---

## Glass Door Stream (Real-Time Visibility)

**Location:** `app/services/glass_door_stream.py`

The Glass Door Stream provides **investor-facing transparency** into AI decision-making. Every agent thought, tool call, decision, and rejection is logged and broadcast via WebSocket.

### Event Types

1. **Thinking** - Agent's reasoning process
   ```python
   await stream.log_thinking(
       "annie",
       "Analyzing available drivers for load...",
       reasoning="Need driver within 50 miles with reefer equipment"
   )
   ```

2. **Tool Call** - When agent uses a function
   ```python
   await stream.log_tool_call(
       "adam",
       "audit_driver_hos",
       {"driver_id": "123", "trip_hours": 8.5},
       reasoning="Validating HOS compliance"
   )
   ```

3. **Decision** - Agent makes a choice
   ```python
   await stream.log_decision(
       "atlas",
       "APPROVED - Margin is 18.5%",
       reasoning="Meets 15% minimum profitability requirement",
       confidence=1.0
   )
   ```

4. **Rejection** - Agent rejects another's proposal
   ```python
   await stream.log_rejection(
       "adam",
       "Driver assignment",
       reason="Driver only has 6.2 hours HOS, needs 10.5 hours",
       suggested_alternative="Find driver with more HOS remaining"
   )
   ```

5. **Result** - Final outcome
   ```python
   await stream.log_result(
       "annie",
       "✅ Load dispatched successfully",
       data={"driver_id": "123", "margin": 18.5}
   )
   ```

6. **Error** - Execution failure
   ```python
   await stream.log_error(
       "fleet_manager",
       "Equipment not found in database",
       context={"truck_id": "TRK-456"}
   )
   ```

### WebSocket Integration

Events are broadcast to all company users via WebSocket:

```python
# In glass_door_stream.py
await manager.send_company_message(
    message={
        "type": "ai_agent_stream",
        "data": {
            "task_id": task_id,
            "agent_type": "annie",
            "event_type": "decision",
            "message": "Assigned driver to load",
            "reasoning": "Best match by location and equipment",
            "severity": "success",
            "timestamp": "2025-12-15T10:30:00Z"
        }
    },
    company_id=company_id
)
```

Frontend receives events in real-time and displays them in the Glass Door UI.

---

## LLM Model Router

**Location:** `app/core/llm_router.py`

The LLM Router intelligently selects between Llama 4 Scout (cheap/fast) and Maverick (expensive/smart) based on agent role.

### Model Selection Logic

```python
def get_model_config(self, agent_role: AgentRole) -> dict:
    if agent_role == "annie":
        return {
            "model_id": "llama-4-scout-17b-instruct",
            "context_window": 10_000_000,  # 10M tokens
            "cost_per_1m_tokens": 0.10,
            "capabilities": ["vision", "10M_context", "fast_inference"]
        }

    elif agent_role in ["adam", "fleet_manager", "cfo_analyst", "harper"]:
        return {
            "model_id": "llama-4-maverick-400b-instruct",
            "context_window": 128_000,
            "cost_per_1m_tokens": 2.50,
            "capabilities": ["deep_reasoning", "MoE", "math", "code"]
        }
```

### Multi-Provider Fallback

Ensures 99.9% uptime with provider hierarchy:

1. **Self-hosted** (future) → vLLM/TGI on dedicated GPUs (lowest cost at scale)
2. **Groq** (primary) → Fast inference, generous free tier (14,400 requests/day)
3. **AWS Bedrock** (fallback) → Enterprise reliability, pay-per-token

### Cost Optimization

**Investor Demo (100 operations/day):**
- Annie: 90 ops × 2K tokens = 180K tokens → **Free** (Groq tier)
- Others: 10 ops × 4K tokens = 40K tokens → **Free** (Groq tier)
- **Total: $0/month**

**Production (1,000 operations/day):**
- Annie: 900 ops × 2K tokens = 1.8M tokens → **$5.40/month**
- Others: 100 ops × 4K tokens = 400K tokens → **$30/month**
- **Total: ~$55/month** (cheaper than 1 hour of human dispatcher)

**Post-Funding (Self-Hosted):**
- 4× H100 GPUs for Maverick + 2× A100 for Scout
- Fixed cost: ~$7,200/month
- **Break-even: 130,000 operations/month**
- At 10K ops/day: **10× cheaper than cloud APIs**

---

## Database Schema

### Core Tables

**ai_agent_stream** - Real-time event logging
```sql
CREATE TABLE ai_agent_stream (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL,
    company_id UUID NOT NULL,
    agent_type VARCHAR NOT NULL,  -- annie, adam, atlas, fleet_manager, harper
    event_type VARCHAR NOT NULL,   -- thinking, tool_call, decision, rejection, result, error
    message TEXT NOT NULL,
    reasoning TEXT,
    metadata JSONB,
    severity VARCHAR,              -- info, warning, error, success
    created_at TIMESTAMP DEFAULT NOW()
);
```

**ai_approval_requests** - Human-in-the-loop approvals
```sql
CREATE TABLE ai_approval_requests (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL,
    agent_type VARCHAR NOT NULL,
    reason TEXT NOT NULL,
    recommendation TEXT,
    urgency VARCHAR NOT NULL,      -- low, medium, high, critical
    amount DECIMAL(10,2),
    estimated_cost DECIMAL(10,2),
    status VARCHAR DEFAULT 'pending',  -- pending, approved, rejected
    reviewed_by UUID,
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**driver_settlements** - Payroll tracking (Harper AI)
```sql
CREATE TABLE driver_settlements (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL,
    driver_id UUID NOT NULL,
    load_id UUID,
    settlement_type VARCHAR NOT NULL,  -- driver_pay, bonus, deduction
    amount DECIMAL(10,2) NOT NULL,
    settlement_date DATE NOT NULL,
    pay_period_start DATE,
    pay_period_end DATE,
    payment_status VARCHAR DEFAULT 'pending',  -- pending, paid, cancelled
    created_at TIMESTAMP DEFAULT NOW()
);
```

**maintenance_work_orders** - Fleet maintenance (Fleet Manager AI)
```sql
CREATE TABLE maintenance_work_orders (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL,
    equipment_id UUID NOT NULL,
    maintenance_type VARCHAR NOT NULL,  -- oil_change, inspection, tire_rotation
    priority VARCHAR NOT NULL,          -- routine, urgent, critical
    scheduled_date TIMESTAMP NOT NULL,
    status VARCHAR DEFAULT 'scheduled', -- scheduled, in_progress, completed, cancelled
    parts_cost DECIMAL(10,2),
    labor_cost DECIMAL(10,2),
    total_cost DECIMAL(10,2),
    created_by_ai BOOLEAN DEFAULT FALSE,
    ai_agent_type VARCHAR,              -- fleet_manager
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Conversational AI Interface

**Location:** `app/services/conversational_ai.py`

Users can chat with any AI agent through a unified conversational interface.

### Agent Selection

```python
# User selects which agent to talk to
ai = ConversationalAI(db, agent_type="harper")

# Agent-specific system prompt is loaded
system_prompt = self.get_system_prompt("harper")

# Tools are registered dynamically
tools = await self.get_tools_for_agent("harper")
```

### Example Conversation with Harper

```
User: "What's the total payroll for this week?"

Harper: [Thinking] Calculating payroll for all active drivers for current pay period...
        [Tool Call] process_weekly_payroll(pay_period_end="2025-12-15")
        [Result] Payroll processed: 47 drivers, $124,580 total gross pay

Harper: This week's payroll is ready:
        - 47 drivers paid
        - Total gross: $124,580
        - Total net: $93,435
        - Payroll taxes: $31,145

        Ready to submit to CheckHQ?

User: "Yes, submit it"

Harper: [Tool Call] submit_to_checkhq(payroll_batch_id="...")
        [Result] ✅ Payroll submitted to CheckHQ successfully

Harper: ✅ Payroll submitted! CheckHQ will process direct deposits by Friday.
```

---

## Environment Variables

**Required for AI System:**

```bash
# Database
DATABASE_URL=postgresql+psycopg://user:pass@host/db

# LLM Providers (Multi-provider fallback)
GROQ_API_KEY=gsk_...                    # Primary provider (free tier)
AWS_REGION=us-east-1                    # Fallback provider
AWS_ACCESS_KEY_ID=AKIA...               # AWS Bedrock access
AWS_SECRET_ACCESS_KEY=...
SELF_HOSTED_LLM_ENDPOINT=               # Future self-hosted (leave empty)

# External APIs
CHECKHQ_API_KEY=...                     # Payroll integration (NOT Gusto)
OPENWEATHER_API_KEY=...                 # Weather for dispatch
GOOGLE_MAPS_API_KEY=...                 # Route optimization

# Database Branching (Future)
NEON_API_KEY=...                        # Safe SQL testing
NEON_PROJECT_ID=...

# Legacy (Backward compatibility)
GOOGLE_AI_API_KEY=AIzaSy...             # Old Gemini integration
```

---

## Deployment & Scaling

### Current Infrastructure

- **Backend:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL via NeonDB (serverless, auto-scaling)
- **WebSocket:** Built into FastAPI for Glass Door Stream
- **LLM:** Groq (primary), AWS Bedrock (fallback)

### Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Load assignment latency | < 10 seconds | ~8 seconds |
| Payroll processing (100 drivers) | < 30 seconds | ~25 seconds |
| Glass Door event delivery | < 500ms | ~200ms |
| Agent uptime | 99.9% | 99.5% |

### Scaling Plan

**Phase 1 (Current):** 100 operations/day, $0/month (free tiers)
**Phase 2:** 1,000 operations/day, $55/month (cloud APIs)
**Phase 3:** 10,000 operations/day, self-hosted GPUs ($7K/month fixed)
**Phase 4:** Unlimited operations, dedicated GPU cluster, <$0.01/operation

---

## Security & Compliance

### Data Protection

- **Audit Trail:** Every AI decision logged to `ai_agent_stream` table
- **Approval Gates:** High-risk actions require human approval
- **Database Safety:** Future NeonDB branching prevents production corruption
- **Access Control:** Agents only access company-scoped data

### DOT Compliance

- **HOS Enforcement:** Adam validates all driver assignments
- **Documentation:** All dispatch actions logged for DOT audits
- **Safety First:** Fleet Manager flags critical equipment issues

### Financial Controls

- **Margin Validation:** Atlas rejects unprofitable loads
- **Cost Approval:** Expenses >$5K require human approval
- **Payroll Accuracy:** Harper flags discrepancies >$500

---

## Investor Talking Points

### 1. Next-Gen AI Stack
"We're Llama 4 native - Scout has 10M token context (6 months of conversation memory), Maverick uses Mixture-of-Experts for expert-level reasoning. We're not locked into OpenAI's pricing."

### 2. Zero Demo Costs
"Our investor demo runs at $0/month using Groq's free tier. Production starts at $55/month - cheaper than one hour of a human dispatcher."

### 3. Full Transparency
"The Glass Door UI shows exactly what AI is thinking in real-time - no black box. Perfect for regulated industries where compliance is everything."

### 4. Multi-Agent Checks & Balances
"No single AI makes critical decisions. Annie proposes, Adam audits for DOT compliance, Atlas validates margins. If any agent rejects, we loop back. It's self-correcting."

### 5. Production Ready Today, Self-Hosted Tomorrow
"This isn't a prototype. Running on production database with real loads and drivers. Post-funding, we'll self-host on GPUs - 10× cheaper at scale."

---

## Future Enhancements

### Q1 2026
- [ ] NeonDB database branching for safe SQL testing
- [ ] Fine-tuning Llama 4 on transportation data
- [ ] Voice interface for drivers (phone-based AI)
- [ ] Multi-lingual support (Spanish for drivers)

### Q2 2026
- [ ] Self-hosted GPU infrastructure (4× H100 + 2× A100)
- [ ] Advanced predictive maintenance (ML-based failure prediction)
- [ ] Automated rate negotiation with brokers
- [ ] Real-time route optimization with traffic

### Q3 2026
- [ ] Agent collaboration learning (improve multi-agent coordination)
- [ ] Custom LLM fine-tuning per customer
- [ ] API marketplace for third-party integrations
- [ ] Mobile app with AI assistant

---

## File Structure

```
fopsbackend/
├── app/
│   ├── core/
│   │   ├── llm_router.py           # Model selection (Scout vs Maverick)
│   │   └── database.py             # Database configuration
│   ├── services/
│   │   ├── annie_ai.py             # AI Dispatcher (Scout 17B)
│   │   ├── adam_ai.py              # Compliance Auditor (Maverick 400B)
│   │   ├── atlas_ai.py             # CFO Analyst (Maverick 400B)
│   │   ├── fleet_manager_ai.py     # Fleet Operations (Maverick 400B)
│   │   ├── harper_ai.py            # HR & Payroll (Maverick 400B)
│   │   ├── agent_orchestrator.py   # Workflow coordinator ("supervisor")
│   │   ├── conversational_ai.py    # Chat interface to all agents
│   │   ├── glass_door_stream.py    # Real-time visibility system
│   │   └── websocket_manager.py    # WebSocket broadcasting
│   └── models/
│       ├── ai_task.py              # AI task tracking
│       └── ...
├── alembic/
│   └── versions/
│       └── 20251215_000001_add_approval_and_maintenance_tables.py
└── AI_ARCHITECTURE.md              # This file
```

---

## Support & Documentation

- **Primary Contact:** Development Team
- **Architecture Questions:** See this document
- **API Documentation:** `/docs` (FastAPI auto-generated)
- **Glass Door UI:** `/ai/investor-demo` (frontend)
- **Agent Chat Interface:** `/ai/talk-to-ai` (frontend)

---

**Last Updated:** December 15, 2025
**Version:** 1.0 (Production-Ready)
**Status:** ✅ All 5 agents operational, orchestrator coordinating workflows

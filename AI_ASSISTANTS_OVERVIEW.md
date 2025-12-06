# FreightOps AI Assistants - System Overview

## The Three AI Assistants

FreightOps uses three specialized AI assistants, each focused on different aspects of the TMS:

### 1. **Alex** - Sales & Analytics AI
**Focus:** CRM, Revenue, and Business Intelligence

**Responsibilities:**
- **Renewal Predictions:** Predicts which contracts are at risk and surfaces upsell opportunities
- **ARR Forecasting:** Forecasts Annual Recurring Revenue impact and trends
- **Renewal Alerts:** Nudges sales reps 120 days before contract end dates
- **KPI Aggregation:** Aggregates fleet, dispatch, and finance KPIs to show business trends
- **Sales Intelligence:** Helps sales team with customer insights and opportunities

**Use Cases:**
- "Which contracts are at risk this quarter?"
- "Show me upsell opportunities for current customers"
- "What's our projected ARR for next quarter?"
- "How are our operational KPIs trending?"

---

### 2. **Annie** - Operations AI
**Focus:** Dispatch, Fleet Operations, and Compliance

**Responsibilities:**
- **Driver/Truck Matching:** Provides intelligent matching suggestions for load assignments
- **HOS Awareness:** Considers Hours of Service when suggesting driver assignments
- **Usage Ledger Logging:** Automatically logs dispatch events for billing and IFTA tracking
- **Pickup Process Guidance:** Walks operations through 7-step pickup workflow
- **Compliance Escalation:** Monitors and escalates compliance and safety events via email, SMS, Slack
- **Fuel Reconciliation:** Automatically reconciles fuel card data with usage ledger
- **Service SLA Monitoring:** Monitors vendor response times and service escalations

**Use Cases:**
- "Which driver should I assign to this load?" (considers HOS, location, equipment)
- "Walk me through the pickup process for load #12345"
- "Has the fuel card data been reconciled for March?"
- "Alert me if any drivers are approaching HOS violations"
- "Show me compliance issues that need immediate attention"

---

### 3. **Atlas** - Monitoring & Analytics AI
**Focus:** Exception Management and Performance Tracking

**Responsibilities:**
- **Exception Monitoring:** Monitors loads, deliveries, and operations for exceptions
- **On-Time Delivery Tracking:** Tracks and alerts on delivery performance metrics
- **Performance Analytics:** Analyzes operational performance across the fleet
- **Alert Management:** Surfaces critical issues that need attention
- **Trend Analysis:** Identifies patterns and anomalies in operations

**Use Cases:**
- "Show me loads with delivery exceptions"
- "What's our on-time delivery rate this week?"
- "Alert me to any loads at risk of being late"
- "What are the main operational issues today?"

---

## Marketing Names vs. Internal Names

The AI assistants are marketed under different brand names:

| Marketing Name | Internal AI | Primary Function |
|---------------|-------------|------------------|
| **FreightBot** | Annie | Load creation, dispatch operations |
| **DataBot** | Annie | OCR/document extraction (already implemented) |
| **Smart Audit & Pay** | Alex + Annie | Billing error detection, rate validation |
| **Auto Check Calls** | Annie | Automated driver check-ins via SMS/email |

---

## Integration Architecture

### Current Status (Phase 1 - COMPLETE ✓)
- ✅ **DataBot OCR Engine:** Gemini-powered document extraction
- ✅ **Usage Tracking:** AI quota system (25 OCR, 100 chat, 200 audit/month)
- ✅ **LoadCreate Transformation:** OCR → LoadCreate schema compatibility

### Phase 2 - AI Chat Assistants (IN PROGRESS)

#### Backend Services Needed:
1. **`alex_ai.py`** - Alex AI service (sales, analytics, forecasting)
2. **`annie_ai.py`** - Annie AI service (operations, dispatch, compliance)
3. **`atlas_ai.py`** - Atlas AI service (monitoring, exceptions, alerts)
4. **`ai_chat.py`** - Unified chat orchestrator (routes to correct AI)

#### Database Models Needed:
1. **`AIConversation`** - Stores chat history
2. **`AIMessage`** - Individual messages with context
3. **`AIContext`** - Per-company/user AI context and preferences

#### API Endpoints Needed:
- `POST /api/ai/chat` - Send message to AI (auto-routes to Alex/Annie/Atlas)
- `GET /api/ai/conversations/{company_id}` - Get conversation history
- `POST /api/ai/alex/analyze` - Specific Alex analysis request
- `POST /api/ai/annie/match` - Specific Annie matching request
- `POST /api/ai/atlas/check` - Specific Atlas monitoring request

#### Frontend Components Needed:
- `AIAssistantChat.tsx` - Main chat interface (already exists as FloatingChat)
- `AIAssistantSelector.tsx` - Switch between Alex, Annie, Atlas
- `AIContextProvider.tsx` - Manage AI state and context

---

## Technical Implementation Strategy

### 1. Shared AI Foundation
- Use Google Gemini 2.5 Flash (cost-effective, fast)
- Implement function calling for structured responses
- Each AI has specialized system prompts and tools

### 2. Context Management
Each AI needs different context:

**Alex Context:**
- Company revenue data, contracts, customer profiles
- Sales pipeline, opportunities, ARR trends
- Historical performance metrics

**Annie Context:**
- Active loads, available drivers/trucks
- Driver HOS status, equipment status
- Fuel data, usage ledger entries
- Compliance requirements and deadlines

**Atlas Context:**
- Load status, delivery windows
- Exception history, performance baselines
- Alert thresholds and rules

### 3. Tool/Function Calling
Each AI has access to specific tools:

**Alex Tools:**
- `get_revenue_forecast()` - ARR projections
- `get_at_risk_contracts()` - Churn prediction
- `get_upsell_opportunities()` - Sales suggestions
- `get_business_kpis()` - Dashboard metrics

**Annie Tools:**
- `match_driver_to_load()` - Assignment suggestions
- `check_hos_compliance()` - Driver availability
- `create_load_from_description()` - Load creation
- `reconcile_fuel_data()` - Fuel card matching
- `send_check_call()` - Driver SMS/email

**Atlas Tools:**
- `get_load_exceptions()` - Problem loads
- `check_delivery_status()` - ETA monitoring
- `get_performance_metrics()` - OTD rates
- `create_alert()` - Exception notifications

---

## Cost Considerations

### Using Gemini 2.5 Flash:
- **Input:** $0.075 per 1M tokens (~750,000 words)
- **Output:** $0.30 per 1M tokens (~750,000 words)
- **Free tier:** 45,000 requests/month

### Estimated Costs per AI Interaction:
- Simple query (100 input + 200 output tokens): **$0.00007**
- Complex analysis (500 input + 1000 output tokens): **$0.00034**

### Monthly Cost for 100 Chat Messages/Company:
- **$0.03 per company** (well within free tier)

---

## Implementation Priority

### Phase 2.1: Annie AI (Operations) - HIGHEST PRIORITY
**Why:** Most customer-facing, immediate value
- Load matching and assignment
- Pickup process guidance
- Email/chat load creation ("FreightBot")
- Check calls automation

### Phase 2.2: Atlas AI (Monitoring) - MEDIUM PRIORITY
**Why:** Proactive value, reduces support load
- Exception monitoring
- Delivery tracking
- Performance alerts

### Phase 2.3: Alex AI (Sales/Analytics) - LOWER PRIORITY
**Why:** Less critical for daily operations
- Revenue forecasting
- Renewal predictions
- Business intelligence

---

## Next Steps

1. ✅ Document AI assistant roles and responsibilities (this file)
2. Create `annie_ai.py` service with tool calling
3. Create AI chat API endpoints
4. Integrate with existing chat UI
5. Test Annie AI with real load creation scenarios
6. Implement Atlas AI monitoring
7. Implement Alex AI analytics
8. Add AI assistant selector to chat UI

---

*Last Updated: December 6, 2025*

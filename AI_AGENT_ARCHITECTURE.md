# FreightOps AI Agent Architecture

## Vision: Autonomous AI Workers

The three AI assistants (Alex, Annie, Atlas) are **autonomous agents** that work like human employees. They don't just answer questions - they execute complete tasks from start to finish without human intervention.

### Key Principle
> "Give an AI a task, it completes it autonomously using tools and APIs, then reports back."

---

## How AI Agents Work

### 1. Task Assignment
**Human:** "Annie, create a load from this email and assign the best driver."

### 2. AI Planning (Internal)
Annie breaks down the task:
```
1. Parse email content
2. Extract customer, pickup, delivery, rate
3. Call LoadCreate API with extracted data
4. Query available drivers (check HOS, location, equipment)
5. Select best driver using matching algorithm
6. Assign driver to load
7. Send confirmation email to customer
8. Log in usage ledger for IFTA
9. Send SMS to driver with load details
10. Report completion to user
```

### 3. Autonomous Execution
Annie executes each step:
- Calls OCR service to extract email data
- Validates and transforms to LoadCreate schema
- Makes API call to create load
- Queries driver database
- Runs matching algorithm
- Updates load with driver assignment
- Sends emails/SMS via notification service
- Creates usage ledger entries

### 4. Completion Report
Annie: "✓ Load #12345 created for Walmart, $850. Assigned to Driver John Smith (Truck #42). Pickup tomorrow 8 AM. Customer and driver notified."

---

## The Three AI Agents

### **Annie** - Operations Agent
**Role:** Autonomous dispatch and operations worker

**Tasks Annie Can Execute:**
1. **Load Creation:**
   - "Create a load from this email/PDF"
   - Extracts data → Creates load → Assigns driver → Notifies parties

2. **Driver Assignment:**
   - "Find the best driver for load #12345"
   - Checks HOS → Location → Equipment → Makes assignment → Notifies driver

3. **Pickup Process:**
   - "Walk through pickup for load #12345"
   - Checks geofence → Verifies BOL → Logs usage → Updates status → Notifies dispatcher

4. **Check Calls:**
   - "Do check calls for all active loads"
   - Sends SMS to all drivers → Collects responses → Updates load status → Escalates issues

5. **Fuel Reconciliation:**
   - "Reconcile March fuel card data"
   - Loads fuel card file → Matches to loads → Creates usage entries → Flags discrepancies

**Tools Annie Uses:**
- LoadCreate API
- Driver query API
- Equipment API
- SMS/Email notification service
- Usage ledger service
- Geofence validation API
- OCR/document extraction service

---

### **Atlas** - Monitoring Agent
**Role:** Autonomous exception management and alerting

**Tasks Atlas Can Execute:**
1. **Delivery Monitoring:**
   - "Monitor all deliveries today and alert on risks"
   - Checks ETA for all loads → Predicts delays → Sends alerts → Escalates critical issues

2. **Exception Detection:**
   - "Find and resolve delivery exceptions"
   - Queries loads with issues → Categorizes problems → Auto-resolves simple cases → Escalates complex ones

3. **Performance Tracking:**
   - "Track OTD rate and alert if below 95%"
   - Calculates daily OTD → Compares to threshold → Identifies problem lanes → Sends report

4. **Proactive Alerts:**
   - "Alert me if any driver will hit HOS violation in next 4 hours"
   - Monitors all drivers → Predicts HOS → Sends early warnings → Suggests replacements

**Tools Atlas Uses:**
- Load tracking API
- GPS/ELD data API
- Alert/notification service
- Analytics calculation engine
- Exception classification ML model

---

### **Alex** - Sales & Analytics Agent
**Role:** Autonomous business intelligence and sales support

**Tasks Alex Can Execute:**
1. **Renewal Management:**
   - "Identify at-risk contracts and create action plan"
   - Queries contracts → Analyzes usage patterns → Predicts churn → Generates outreach emails → Schedules follow-ups

2. **Revenue Forecasting:**
   - "Forecast Q2 ARR and identify growth opportunities"
   - Pulls revenue data → Runs forecast model → Identifies upsell targets → Creates sales targets → Generates report

3. **KPI Reporting:**
   - "Generate executive dashboard for this month"
   - Aggregates all KPIs → Calculates trends → Creates visualizations → Sends report → Highlights key insights

4. **Upsell Identification:**
   - "Find customers ready to upgrade to Enterprise plan"
   - Analyzes usage patterns → Identifies feature limits being hit → Scores upgrade likelihood → Creates sales opportunities

**Tools Alex Uses:**
- Revenue analytics API
- Contract database queries
- Forecasting ML models
- Customer usage analytics
- Email/CRM integration

---

## Technical Architecture

### Core Components

#### 1. **AI Agent Engine** (`ai_agent.py`)
Base class for all AI agents with:
- Task parsing and planning
- Tool/function calling
- Step-by-step execution
- Error handling and retry logic
- Progress tracking and reporting

#### 2. **Tool Registry** (`ai_tools.py`)
Registry of all tools available to AI agents:
```python
ANNIE_TOOLS = [
    create_load_tool,
    assign_driver_tool,
    send_notification_tool,
    check_hos_tool,
    create_usage_entry_tool,
    validate_geofence_tool,
]

ATLAS_TOOLS = [
    query_loads_tool,
    check_delivery_eta_tool,
    create_alert_tool,
    calculate_metrics_tool,
]

ALEX_TOOLS = [
    query_revenue_tool,
    forecast_arr_tool,
    analyze_churn_risk_tool,
    create_opportunity_tool,
]
```

#### 3. **Task Queue** (`ai_tasks.py`)
Manages AI task execution:
- Task queuing with priority
- Async task execution
- Progress tracking
- Result storage
- Error handling

#### 4. **Task Models** (`models/ai_task.py`)
Database models for tracking AI tasks:
```python
class AITask:
    id: str
    company_id: str
    agent_type: str  # annie, atlas, alex
    task_description: str
    status: str  # queued, in_progress, completed, failed
    steps: JSON  # List of planned steps
    current_step: int
    result: JSON
    error: str
    created_at: datetime
    started_at: datetime
    completed_at: datetime
```

---

## Example: Annie Creates a Load Autonomously

### User Input:
```
"Annie, create a load from this email"
[Email attached with rate confirmation]
```

### Annie's Execution Flow:

```python
# Step 1: Parse task
task = parse_task("create a load from this email")
# → Task type: load_creation
# → Input: email content

# Step 2: Plan steps
steps = [
    {"action": "extract_data", "tool": "ocr_service", "input": email_content},
    {"action": "validate_data", "tool": "data_validator"},
    {"action": "create_load", "tool": "load_api", "input": extracted_data},
    {"action": "find_driver", "tool": "driver_matcher", "input": load_requirements},
    {"action": "assign_driver", "tool": "load_api", "input": {load_id, driver_id}},
    {"action": "notify_customer", "tool": "email_service"},
    {"action": "notify_driver", "tool": "sms_service"},
    {"action": "log_usage", "tool": "usage_ledger"},
]

# Step 3: Execute each step
for step in steps:
    try:
        result = execute_tool(step["tool"], step["input"])
        step["status"] = "completed"
        step["result"] = result
    except Exception as e:
        step["status"] = "failed"
        step["error"] = str(e)
        # Try to auto-recover or escalate
        if can_retry(e):
            retry_step(step)
        else:
            escalate_to_human(step, e)
            break

# Step 4: Report completion
return {
    "status": "completed",
    "load_id": "12345",
    "driver_assigned": "John Smith",
    "notifications_sent": ["customer@walmart.com", "+1-555-0100"],
    "summary": "Load #12345 created for Walmart, $850. Pickup tomorrow 8 AM at Baytown, TX."
}
```

---

## AI Agent Communication Protocol

### Input Format:
```json
{
  "agent": "annie",
  "task": "create load from email",
  "input": {
    "email_content": "...",
    "attachments": ["rate_con.pdf"]
  },
  "priority": "normal",
  "deadline": "2025-12-06T17:00:00Z"
}
```

### Progress Updates:
```json
{
  "task_id": "task_123",
  "status": "in_progress",
  "current_step": 3,
  "total_steps": 8,
  "step_description": "Assigning driver to load",
  "progress_percent": 37
}
```

### Completion Response:
```json
{
  "task_id": "task_123",
  "status": "completed",
  "result": {
    "load_id": "12345",
    "driver_id": "67890",
    "notifications_sent": 3,
    "summary": "Load created and assigned successfully"
  },
  "execution_time_seconds": 12.4,
  "tools_used": ["ocr_service", "load_api", "driver_matcher", "sms_service"]
}
```

---

## Implementation Strategy

### Phase 1: Foundation (Current)
1. ✅ Create AI task models
2. ✅ Create AI agent base class
3. Create tool registry system
4. Create task queue manager

### Phase 2: Annie Implementation
1. Implement Annie agent with all tools
2. Test load creation workflow
3. Test driver assignment workflow
4. Test check calls workflow
5. Test fuel reconciliation workflow

### Phase 3: Atlas Implementation
1. Implement Atlas monitoring agent
2. Test exception detection
3. Test delivery monitoring
4. Test performance alerts

### Phase 4: Alex Implementation
1. Implement Alex sales/analytics agent
2. Test revenue forecasting
3. Test churn prediction
4. Test KPI aggregation

### Phase 5: UI & Monitoring
1. Create AI task dashboard
2. Add real-time progress monitoring
3. Add task history and logs
4. Add manual task assignment interface

---

## Key Differences from Traditional Chatbots

| Chatbots | Autonomous AI Agents |
|----------|---------------------|
| Answer questions | Execute complete tasks |
| Require step-by-step guidance | Plan and execute autonomously |
| Passive | Proactive |
| User drives conversation | AI drives execution |
| Limited to chat interface | Uses all available APIs/tools |
| No state between messages | Maintains task state throughout execution |
| Can't make changes | Makes changes to database, sends emails, etc. |

---

## Success Metrics

### Annie Success:
- % of loads created without human intervention
- Driver assignment accuracy (accepted vs. rejected)
- Time saved vs. manual dispatch
- Error rate in data extraction

### Atlas Success:
- % of exceptions caught proactively
- False positive rate on alerts
- Average time to detect issues
- Delivery delay prediction accuracy

### Alex Success:
- Churn prediction accuracy
- Forecast error margin
- Upsell conversion rate from recommendations
- Time saved in manual reporting

---

*This is the future of TMS - AI workers that handle operations autonomously, freeing humans for strategic decisions.*

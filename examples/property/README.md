# 🏠 Property Management

> AI assistants for property managers, tenants, landlords, and strata.

## Examples

| # | Example | Description | Level |
|---|---------|-------------|-------|
| 55 | [property_manager.py](55_property_manager.py) | Property management AI | 🟡 Intermediate |
| 56 | [tenant_portal.py](56_tenant_portal.py) | Tenant self-service | 🟡 Intermediate |
| 57 | [landlord_portal.py](57_landlord_portal.py) | Landlord dashboard | 🟡 Intermediate |
| 58 | [property_maintenance.py](58_property_maintenance.py) | Maintenance requests | 🟡 Intermediate |
| 59 | [strata_manager.py](59_strata_manager.py) | Strata/body corporate | 🟡 Intermediate |

## Quick Start

```bash
# Property management
python examples/property/55_property_manager.py

# Tenant portal
python examples/property/56_tenant_portal.py

# Maintenance system
python examples/property/58_property_maintenance.py
```

## Use Cases

### Property Management
- Property portfolio overview
- Tenant screening queries
- Lease management
- Rent collection tracking
- Inspection scheduling
- Vacancy management

### Tenant Portal
- Rent payment history
- Maintenance requests
- Lease information
- Communication with manager
- Document access
- Move-out procedures

### Landlord Portal
- Property performance
- Financial reports
- Tenant information
- Maintenance approvals
- Market analysis
- Investment insights

### Maintenance System
- Request submission
- Contractor assignment
- Status tracking
- Cost management
- Preventive scheduling
- Work order management

### Strata Management
- Levy tracking
- Meeting management
- By-law queries
- Maintenance fund
- Common area issues
- Owner communications

## Common Patterns

### Property Manager Agent
```python
from agentic_brain import Agent

agent = Agent(
    name="property_manager",
    tools=[
        search_properties,
        get_tenant_info,
        schedule_inspection,
        process_application,
        generate_report
    ],
    system_prompt="""You are a property management assistant.
    Help with:
    - Property queries and availability
    - Tenant information (respect privacy)
    - Maintenance coordination
    - Financial reporting"""
)
```

### Maintenance Workflow
```python
def create_maintenance_request(property_id, issue, priority):
    # Log request
    request_id = log_request(property_id, issue, priority)
    
    # AI categorization
    category = agent.chat(f"Categorize this issue: {issue}")
    
    # Find contractor
    contractor = find_contractor(category, property_id)
    
    # Notify parties
    notify_tenant(request_id)
    notify_landlord(request_id)
    notify_contractor(request_id)
    
    return request_id
```

### Rent Analysis
```python
def analyze_rent(property_id):
    market_data = get_market_data(property_id)
    current_rent = get_current_rent(property_id)
    
    analysis = agent.chat(f"""
    Analyze rent for property {property_id}:
    - Current rent: ${current_rent}/week
    - Market data: {market_data}
    
    Provide recommendation for rent review.
    """)
    return analysis
```

## Australian Specific

### Residential Tenancies
- State-specific legislation
- Bond management
- Notice periods
- Rent increase rules
- Dispute resolution

### Strata Titles
- Body corporate rules
- Sinking fund
- Lot entitlements
- Common property
- AGM requirements

## Integration Points

- **Property Software**: PropertyMe, Console, Rockend
- **Payment**: DEFT, Bpay
- **Inspections**: Inspection Express
- **Background Checks**: TICA, NTD

## Prerequisites

- Python 3.10+
- Ollama running locally
- Neo4j (for property graph)
- Property management API access (optional)

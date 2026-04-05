#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Banking & Finance Assistant
===========================

An AI assistant for banking operations including account inquiries,
transaction history, budget analysis, and investment basics.

Features:
- Account balance and information
- Transaction history and search
- Budget analysis and tracking
- Spending insights
- Investment education

Run:
    python examples/46_finance_banking.py

DISCLAIMER:
    This is a demonstration system with simulated data.
    Not for actual financial transactions or advice.
    Consult a qualified financial advisor for real financial decisions.
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Any

from agentic_brain import Agent

# ============================================================================
# Demo Banking Data
# ============================================================================

ACCOUNTS = {
    "CHK-001": {
        "type": "Checking",
        "name": "Primary Checking",
        "balance": 5847.32,
        "available_balance": 5647.32,
        "pending_transactions": 200.00,
        "account_number": "****4521",
        "routing_number": "****7890",
        "interest_rate": 0.01,
        "opened_date": "2019-03-15",
        "overdraft_protection": True,
    },
    "SAV-001": {
        "type": "Savings",
        "name": "Emergency Fund",
        "balance": 12450.00,
        "available_balance": 12450.00,
        "pending_transactions": 0,
        "account_number": "****4522",
        "interest_rate": 0.50,
        "opened_date": "2019-03-15",
        "monthly_withdrawal_limit": 6,
        "withdrawals_this_month": 1,
    },
    "SAV-002": {
        "type": "Savings",
        "name": "Vacation Fund",
        "balance": 3200.00,
        "available_balance": 3200.00,
        "pending_transactions": 0,
        "account_number": "****4523",
        "interest_rate": 0.50,
        "opened_date": "2021-06-01",
        "goal": 5000.00,
        "progress": 64.0,
    },
    "CC-001": {
        "type": "Credit Card",
        "name": "Rewards Card",
        "balance": -1847.50,
        "credit_limit": 10000.00,
        "available_credit": 8152.50,
        "account_number": "****8901",
        "interest_rate": 18.99,
        "rewards_points": 24750,
        "minimum_payment": 35.00,
        "due_date": "2024-02-15",
        "statement_balance": 1650.00,
    },
}


# Generate sample transactions
def _generate_transactions():
    categories = {
        "Groceries": ["Whole Foods", "Trader Joe's", "Safeway", "Costco"],
        "Dining": ["Starbucks", "Chipotle", "Pizza Place", "Thai Restaurant"],
        "Transportation": ["Shell Gas", "Uber", "Lyft", "Metro Card"],
        "Shopping": ["Amazon", "Target", "Best Buy", "Home Depot"],
        "Bills": ["Electric Co", "Water Utility", "Internet Provider", "Phone Bill"],
        "Entertainment": ["Netflix", "Spotify", "Movie Theater", "Concert Tickets"],
        "Healthcare": ["Pharmacy", "Doctor Visit", "Dental Care"],
        "Income": ["Employer Payroll", "Freelance Payment", "Refund"],
    }

    transactions = []
    base_date = datetime.now()

    for i in range(60):
        days_ago = random.randint(0, 90)
        date = base_date - timedelta(days=days_ago)

        if random.random() < 0.1:  # 10% chance of income
            category = "Income"
            amount = random.choice([2500.00, 3000.00, 150.00, 500.00])
        else:
            category = random.choice(list(categories.keys())[:-1])
            if category == "Groceries":
                amount = -random.uniform(30, 200)
            elif category == "Dining":
                amount = -random.uniform(8, 75)
            elif category == "Transportation":
                amount = -random.uniform(20, 80)
            elif category == "Shopping":
                amount = -random.uniform(25, 300)
            elif category == "Bills":
                amount = -random.uniform(50, 200)
            elif category == "Entertainment":
                amount = -random.uniform(10, 100)
            else:
                amount = -random.uniform(25, 150)

        merchant = random.choice(categories[category])

        transactions.append(
            {
                "id": f"TXN{i:05d}",
                "date": date.strftime("%Y-%m-%d"),
                "description": merchant,
                "category": category,
                "amount": round(amount, 2),
                "account": (
                    "CHK-001"
                    if category != "Shopping"
                    else random.choice(["CHK-001", "CC-001"])
                ),
                "status": "Posted" if days_ago > 1 else "Pending",
            }
        )

    transactions.sort(key=lambda x: x["date"], reverse=True)
    return transactions


TRANSACTIONS = _generate_transactions()

# Budget data
BUDGET = {
    "Groceries": {"limit": 500, "spent": 0},
    "Dining": {"limit": 200, "spent": 0},
    "Transportation": {"limit": 300, "spent": 0},
    "Shopping": {"limit": 400, "spent": 0},
    "Bills": {"limit": 600, "spent": 0},
    "Entertainment": {"limit": 150, "spent": 0},
    "Healthcare": {"limit": 200, "spent": 0},
}

# Calculate budget spent from transactions
for txn in TRANSACTIONS:
    if txn["category"] in BUDGET and txn["amount"] < 0:
        month_ago = datetime.now() - timedelta(days=30)
        if datetime.strptime(txn["date"], "%Y-%m-%d") > month_ago:
            BUDGET[txn["category"]]["spent"] += abs(txn["amount"])


# ============================================================================
# Banking Tools
# ============================================================================


def get_accounts() -> dict[str, Any]:
    """
    Get all account information and balances.

    Returns:
        List of accounts with balances
    """
    accounts_list = []
    total_assets = 0
    total_liabilities = 0

    for acc_id, acc in ACCOUNTS.items():
        accounts_list.append(
            {
                "id": acc_id,
                "name": acc["name"],
                "type": acc["type"],
                "balance": acc["balance"],
                "available": acc.get("available_balance", acc.get("available_credit")),
            }
        )

        if acc["balance"] > 0:
            total_assets += acc["balance"]
        else:
            total_liabilities += abs(acc["balance"])

    return {
        "accounts": accounts_list,
        "summary": {
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2),
            "net_worth": round(total_assets - total_liabilities, 2),
        },
    }


def get_account_details(account_id: str) -> dict[str, Any]:
    """
    Get detailed information about a specific account.

    Args:
        account_id: Account ID (e.g., CHK-001, SAV-001, CC-001)

    Returns:
        Account details
    """
    account_id = account_id.upper()

    if account_id not in ACCOUNTS:
        return {
            "error": f"Account {account_id} not found",
            "available_accounts": list(ACCOUNTS.keys()),
        }

    return {
        "account_id": account_id,
        **ACCOUNTS[account_id],
    }


def get_transactions(
    account_id: str = None,
    category: str = None,
    days: int = 30,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Get transaction history.

    Args:
        account_id: Filter by account ID
        category: Filter by category
        days: Number of days to look back
        limit: Maximum transactions to return

    Returns:
        Transaction list
    """
    cutoff_date = datetime.now() - timedelta(days=days)

    filtered = []
    for txn in TRANSACTIONS:
        txn_date = datetime.strptime(txn["date"], "%Y-%m-%d")

        if txn_date < cutoff_date:
            continue
        if account_id and txn["account"] != account_id.upper():
            continue
        if category and txn["category"].lower() != category.lower():
            continue

        filtered.append(txn)

        if len(filtered) >= limit:
            break

    # Calculate summary
    total_income = sum(t["amount"] for t in filtered if t["amount"] > 0)
    total_expenses = sum(t["amount"] for t in filtered if t["amount"] < 0)

    return {
        "filters": {
            "account": account_id,
            "category": category,
            "days": days,
        },
        "transactions": filtered,
        "summary": {
            "count": len(filtered),
            "total_income": round(total_income, 2),
            "total_expenses": round(abs(total_expenses), 2),
            "net": round(total_income + total_expenses, 2),
        },
    }


def search_transactions(
    query: str,
    min_amount: float = None,
    max_amount: float = None,
) -> dict[str, Any]:
    """
    Search transactions by description or amount.

    Args:
        query: Search term for description
        min_amount: Minimum amount
        max_amount: Maximum amount

    Returns:
        Matching transactions
    """
    results = []

    for txn in TRANSACTIONS:
        if query.lower() not in txn["description"].lower():
            continue

        amount = abs(txn["amount"])
        if min_amount and amount < min_amount:
            continue
        if max_amount and amount > max_amount:
            continue

        results.append(txn)

    return {
        "query": query,
        "results": results[:20],
        "total_found": len(results),
    }


def get_spending_analysis(days: int = 30) -> dict[str, Any]:
    """
    Analyze spending patterns by category.

    Args:
        days: Number of days to analyze

    Returns:
        Spending breakdown by category
    """
    cutoff_date = datetime.now() - timedelta(days=days)

    by_category = {}
    total_spending = 0

    for txn in TRANSACTIONS:
        if txn["amount"] >= 0:
            continue

        txn_date = datetime.strptime(txn["date"], "%Y-%m-%d")
        if txn_date < cutoff_date:
            continue

        category = txn["category"]
        amount = abs(txn["amount"])

        if category not in by_category:
            by_category[category] = {"amount": 0, "count": 0, "transactions": []}

        by_category[category]["amount"] += amount
        by_category[category]["count"] += 1
        by_category[category]["transactions"].append(txn["description"])
        total_spending += amount

    # Calculate percentages and round
    analysis = []
    for category, data in sorted(
        by_category.items(), key=lambda x: x[1]["amount"], reverse=True
    ):
        analysis.append(
            {
                "category": category,
                "amount": round(data["amount"], 2),
                "percentage": (
                    round(data["amount"] / total_spending * 100, 1)
                    if total_spending > 0
                    else 0
                ),
                "transaction_count": data["count"],
                "top_merchants": list(set(data["transactions"]))[:3],
            }
        )

    return {
        "period": f"Last {days} days",
        "total_spending": round(total_spending, 2),
        "daily_average": round(total_spending / days, 2),
        "by_category": analysis,
        "insights": _generate_spending_insights(analysis),
    }


def _generate_spending_insights(analysis: list) -> list[str]:
    """Generate insights based on spending patterns."""
    insights = []

    if analysis:
        top = analysis[0]
        insights.append(
            f"Your highest spending category is {top['category']} at ${top['amount']:.2f}"
        )

        for cat in analysis:
            if cat["percentage"] > 30:
                insights.append(
                    f"Consider reviewing {cat['category']} spending - it's {cat['percentage']}% of your total"
                )

    return insights


def get_budget_status() -> dict[str, Any]:
    """
    Get current month's budget status.

    Returns:
        Budget limits vs actual spending
    """
    budget_status = []
    total_limit = 0
    total_spent = 0

    for category, data in BUDGET.items():
        spent = round(data["spent"], 2)
        limit = data["limit"]
        remaining = limit - spent
        percentage = round(spent / limit * 100, 1) if limit > 0 else 0

        status = "On Track"
        if percentage >= 100:
            status = "Over Budget"
        elif percentage >= 80:
            status = "Warning"

        budget_status.append(
            {
                "category": category,
                "limit": limit,
                "spent": spent,
                "remaining": round(remaining, 2),
                "percentage": percentage,
                "status": status,
            }
        )

        total_limit += limit
        total_spent += spent

    return {
        "month": datetime.now().strftime("%B %Y"),
        "categories": sorted(
            budget_status, key=lambda x: x["percentage"], reverse=True
        ),
        "total_budget": total_limit,
        "total_spent": round(total_spent, 2),
        "total_remaining": round(total_limit - total_spent, 2),
    }


def set_budget(category: str, limit: float) -> dict[str, Any]:
    """
    Set or update a budget limit for a category.

    Args:
        category: Spending category
        limit: Monthly limit amount

    Returns:
        Updated budget
    """
    category = category.title()

    if category not in BUDGET:
        BUDGET[category] = {"limit": 0, "spent": 0}

    old_limit = BUDGET[category]["limit"]
    BUDGET[category]["limit"] = limit

    return {
        "success": True,
        "category": category,
        "old_limit": old_limit,
        "new_limit": limit,
        "message": f"Budget for {category} updated to ${limit:.2f}/month",
    }


def transfer_funds(
    from_account: str,
    to_account: str,
    amount: float,
    memo: str = "",
) -> dict[str, Any]:
    """
    Transfer funds between accounts.

    Args:
        from_account: Source account ID
        to_account: Destination account ID
        amount: Transfer amount
        memo: Optional memo

    Returns:
        Transfer confirmation

    DISCLAIMER: This is a simulation only.
    """
    from_account = from_account.upper()
    to_account = to_account.upper()

    if from_account not in ACCOUNTS:
        return {"error": f"Source account {from_account} not found"}
    if to_account not in ACCOUNTS:
        return {"error": f"Destination account {to_account} not found"}

    source = ACCOUNTS[from_account]
    available = source.get("available_balance", source.get("balance", 0))

    if amount > available:
        return {
            "error": "Insufficient funds",
            "available_balance": available,
            "requested_amount": amount,
        }

    # Simulate transfer (don't actually modify for demo)
    transfer_id = f"TRF{random.randint(100000, 999999)}"

    return {
        "success": True,
        "transfer_id": transfer_id,
        "from_account": from_account,
        "to_account": to_account,
        "amount": amount,
        "memo": memo,
        "status": "Completed",
        "timestamp": datetime.now().isoformat(),
        "disclaimer": "This is a simulated transfer for demonstration purposes only.",
    }


def get_bills_summary() -> dict[str, Any]:
    """
    Get upcoming bills and payment summary.

    Returns:
        Bills due and recent payments
    """
    bills = [
        {
            "name": "Electric Co",
            "amount": 145.00,
            "due_date": "2024-02-10",
            "status": "Due Soon",
            "autopay": True,
        },
        {
            "name": "Internet Provider",
            "amount": 79.99,
            "due_date": "2024-02-15",
            "status": "Upcoming",
            "autopay": True,
        },
        {
            "name": "Phone Bill",
            "amount": 85.00,
            "due_date": "2024-02-18",
            "status": "Upcoming",
            "autopay": False,
        },
        {
            "name": "Water Utility",
            "amount": 45.00,
            "due_date": "2024-02-20",
            "status": "Upcoming",
            "autopay": True,
        },
        {
            "name": "Credit Card",
            "amount": 1650.00,
            "due_date": "2024-02-15",
            "status": "Due Soon",
            "autopay": False,
        },
    ]

    total_due = sum(b["amount"] for b in bills)
    autopay_total = sum(b["amount"] for b in bills if b["autopay"])

    return {
        "upcoming_bills": bills,
        "total_due_this_month": round(total_due, 2),
        "autopay_enabled": round(autopay_total, 2),
        "manual_payment_needed": round(total_due - autopay_total, 2),
    }


def get_investment_basics(topic: str = None) -> dict[str, Any]:
    """
    Get educational information about investing basics.

    Args:
        topic: Specific topic (stocks, bonds, funds, retirement)

    Returns:
        Educational content

    DISCLAIMER: This is educational content only, not financial advice.
    """
    topics = {
        "stocks": {
            "description": "Stocks represent ownership shares in a company.",
            "key_points": [
                "Potential for higher returns but also higher risk",
                "Value fluctuates based on company performance and market conditions",
                "Can earn dividends if company distributes profits",
                "Best suited for long-term investing",
            ],
            "risks": [
                "Market volatility",
                "Company-specific risks",
                "Potential for loss",
            ],
        },
        "bonds": {
            "description": "Bonds are loans to companies or governments that pay interest.",
            "key_points": [
                "Generally lower risk than stocks",
                "Provide regular interest payments",
                "Return of principal at maturity",
                "Prices move inversely to interest rates",
            ],
            "risks": ["Interest rate risk", "Credit/default risk", "Inflation risk"],
        },
        "mutual_funds": {
            "description": "Mutual funds pool money from many investors to buy diversified investments.",
            "key_points": [
                "Professional management",
                "Instant diversification",
                "Various types: stock, bond, balanced",
                "Fees vary - check expense ratios",
            ],
            "risks": ["Market risk", "Management risk", "Fee impact on returns"],
        },
        "etfs": {
            "description": "ETFs (Exchange-Traded Funds) trade like stocks but hold diversified assets.",
            "key_points": [
                "Trade throughout the day like stocks",
                "Often lower fees than mutual funds",
                "Tax efficient",
                "Wide variety available",
            ],
            "risks": ["Market risk", "Trading costs", "Tracking error"],
        },
        "retirement": {
            "description": "Tax-advantaged accounts for retirement savings.",
            "key_points": [
                "401(k): Employer-sponsored, often with matching",
                "IRA: Individual retirement account",
                "Roth: After-tax contributions, tax-free growth",
                "Start early to maximize compound growth",
            ],
            "tips": [
                "Contribute at least enough to get employer match",
                "Increase contributions over time",
                "Consider target-date funds for simplicity",
            ],
        },
    }

    if topic and topic.lower() in topics:
        return {
            "topic": topic,
            **topics[topic.lower()],
            "disclaimer": "This is educational content only. Consult a financial advisor for personalized advice.",
        }

    return {
        "available_topics": list(topics.keys()),
        "overview": {
            "stocks": "Ownership in companies - higher risk/reward",
            "bonds": "Loans to entities - generally lower risk",
            "mutual_funds": "Professionally managed diversified portfolios",
            "etfs": "Traded funds with diversification benefits",
            "retirement": "Tax-advantaged retirement savings options",
        },
        "disclaimer": "This is educational content only. Consult a financial advisor for personalized advice.",
    }


def calculate_savings_goal(
    goal_amount: float,
    current_savings: float = 0,
    monthly_contribution: float = 0,
    annual_return: float = 0.05,
) -> dict[str, Any]:
    """
    Calculate time to reach a savings goal.

    Args:
        goal_amount: Target amount
        current_savings: Starting amount
        monthly_contribution: Monthly savings amount
        annual_return: Expected annual return (default 5%)

    Returns:
        Projection of goal timeline
    """
    monthly_rate = annual_return / 12
    balance = current_savings
    months = 0
    projections = []

    while balance < goal_amount and months < 600:  # Max 50 years
        months += 1
        balance = balance * (1 + monthly_rate) + monthly_contribution

        if months % 12 == 0:
            projections.append(
                {
                    "year": months // 12,
                    "balance": round(balance, 2),
                    "progress": round(balance / goal_amount * 100, 1),
                }
            )

    years = months / 12
    total_contributions = current_savings + (monthly_contribution * months)
    interest_earned = balance - total_contributions

    return {
        "goal": goal_amount,
        "current_savings": current_savings,
        "monthly_contribution": monthly_contribution,
        "annual_return": f"{annual_return * 100}%",
        "time_to_goal": f"{years:.1f} years ({months} months)",
        "total_contributions": round(total_contributions, 2),
        "interest_earned": round(interest_earned, 2),
        "yearly_projections": projections[:10],
        "tip": "Increasing your monthly contribution can significantly reduce time to goal.",
    }


# ============================================================================
# Agent Configuration
# ============================================================================

BANKING_TOOLS = [
    {
        "name": "get_accounts",
        "description": "Get all account balances and net worth summary",
        "function": get_accounts,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_account_details",
        "description": "Get detailed information about a specific account",
        "function": get_account_details,
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "Account ID (CHK-001, SAV-001, CC-001)",
                },
            },
            "required": ["account_id"],
        },
    },
    {
        "name": "get_transactions",
        "description": "Get transaction history with optional filters",
        "function": get_transactions,
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Filter by account"},
                "category": {"type": "string", "description": "Filter by category"},
                "days": {"type": "integer", "description": "Days to look back"},
                "limit": {"type": "integer", "description": "Max transactions"},
            },
        },
    },
    {
        "name": "search_transactions",
        "description": "Search transactions by description or amount",
        "function": search_transactions,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "min_amount": {"type": "number", "description": "Minimum amount"},
                "max_amount": {"type": "number", "description": "Maximum amount"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_spending_analysis",
        "description": "Analyze spending patterns by category",
        "function": get_spending_analysis,
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days to analyze"},
            },
        },
    },
    {
        "name": "get_budget_status",
        "description": "Get current month's budget status",
        "function": get_budget_status,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "set_budget",
        "description": "Set or update a budget limit for a category",
        "function": set_budget,
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Spending category"},
                "limit": {"type": "number", "description": "Monthly limit"},
            },
            "required": ["category", "limit"],
        },
    },
    {
        "name": "transfer_funds",
        "description": "Transfer funds between accounts (simulation only)",
        "function": transfer_funds,
        "parameters": {
            "type": "object",
            "properties": {
                "from_account": {"type": "string", "description": "Source account ID"},
                "to_account": {
                    "type": "string",
                    "description": "Destination account ID",
                },
                "amount": {"type": "number", "description": "Transfer amount"},
                "memo": {"type": "string", "description": "Optional memo"},
            },
            "required": ["from_account", "to_account", "amount"],
        },
    },
    {
        "name": "get_bills_summary",
        "description": "Get upcoming bills and payment summary",
        "function": get_bills_summary,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_investment_basics",
        "description": "Get educational information about investing",
        "function": get_investment_basics,
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic: stocks, bonds, funds, etfs, retirement",
                },
            },
        },
    },
    {
        "name": "calculate_savings_goal",
        "description": "Calculate time to reach a savings goal",
        "function": calculate_savings_goal,
        "parameters": {
            "type": "object",
            "properties": {
                "goal_amount": {"type": "number", "description": "Target amount"},
                "current_savings": {"type": "number", "description": "Starting amount"},
                "monthly_contribution": {
                    "type": "number",
                    "description": "Monthly savings",
                },
                "annual_return": {
                    "type": "number",
                    "description": "Expected return rate",
                },
            },
            "required": ["goal_amount"],
        },
    },
]

SYSTEM_PROMPT = """You are a helpful banking assistant providing account information and financial guidance.

Your capabilities:
- Show account balances and details
- Display transaction history
- Analyze spending patterns
- Track budgets
- Help with fund transfers (simulation)
- Explain investment basics
- Calculate savings goals

Guidelines:
- Always be clear this is a demonstration with simulated data
- Never provide specific investment recommendations
- Encourage users to consult financial advisors for real decisions
- Be helpful in explaining financial concepts
- Prioritize security - never ask for or display full account numbers
- Help users understand their spending habits

IMPORTANT DISCLAIMERS:
- This is a demonstration system only
- All data shown is simulated
- Do not provide personalized investment advice
- Recommend consulting qualified financial advisors
- This is not a real banking system

Available accounts: CHK-001 (Checking), SAV-001 (Emergency Fund), SAV-002 (Vacation Fund), CC-001 (Credit Card)"""


# ============================================================================
# Main Application
# ============================================================================


async def main():
    """Run the Banking & Finance Assistant."""
    print("=" * 60)
    print("🏦 Banking & Finance Assistant")
    print("=" * 60)
    print("\n⚠️  DEMO MODE - Simulated data only")
    print("    Not connected to real banking systems\n")
    print("I can help you with:")
    print("  • Account balances and details")
    print("  • Transaction history and search")
    print("  • Spending analysis and budgets")
    print("  • Investment education")
    print("  • Savings goal calculations")
    print("\n💡 Example questions:")
    print('  "What are my account balances?"')
    print('  "Show my recent transactions"')
    print('  "Analyze my spending"')
    print('  "Explain stocks vs bonds"')
    print("\nType 'quit' to exit")
    print("-" * 60)

    # Create agent
    agent = Agent(
        name="banking_assistant",
        system_prompt=SYSTEM_PROMPT,
        tools=BANKING_TOOLS,
    )

    try:
        while True:
            user_input = input("\n💳 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("\n👋 Thank you for banking with us!")
                break

            # Special commands
            if user_input.lower() == "accounts":
                accts = get_accounts()
                print("\n📊 Your Accounts:")
                for a in accts["accounts"]:
                    print(f"  {a['id']}: {a['name']} - ${a['balance']:,.2f}")
                print(f"\n  Net Worth: ${accts['summary']['net_worth']:,.2f}")
                continue

            if user_input.lower() == "budget":
                budget = get_budget_status()
                print(f"\n📋 Budget Status ({budget['month']}):")
                for cat in budget["categories"][:5]:
                    bar = "█" * int(cat["percentage"] / 10) + "░" * (
                        10 - int(cat["percentage"] / 10)
                    )
                    print(f"  {cat['category']}: [{bar}] {cat['percentage']}%")
                continue

            # Get response from agent
            response = await agent.chat_async(user_input)
            print(f"\n🤖 Agent: {response}")

    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

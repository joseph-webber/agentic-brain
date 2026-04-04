# Security Patterns for Autonomous Agents

## The WordPress Lesson

What we learned from WordPress/WooCommerce chatbot security:

1. **GUEST mirrors platform guest** - Only public APIs + help
2. **USER mirrors platform user** - Own-data APIs only
3. **SAFE_ADMIN mirrors trusted operators** - Machine access with guardrails
4. **FULL_ADMIN mirrors the owner** - Unrestricted machine + platform access

## Applying to Any Integration

This pattern works for any platform:

| Role | Stripe | Shopify | Slack | Custom |
|------|--------|---------|-------|--------|
| GUEST | View products | Browse store | - | Help only |
| USER | Own payments | Own orders | Own messages | Role APIs |
| SAFE_ADMIN | Integration maintenance | App configuration | Workspace administration with confirmations | Protected machine access |
| FULL_ADMIN | All accounts | Store owner | Workspace owner | Everything |

## Blocked for Non-Machine Roles

- Web searches (expensive, can thrash system)
- Code execution
- File system access
- System commands
- Heavy LLM calls

## Rate Limiting

- GUEST: 10/min
- USER: 60/min
- SAFE_ADMIN: 1000/min
- FULL_ADMIN: none

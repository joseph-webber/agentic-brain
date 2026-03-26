# LLM Guide

This guide explains how Agentic Brain routes work across different LLM providers, along with
persona-driven safety and tone controls. Use these references when selecting the best model
and persona for a workflow or when extending the router.

---

### Router Templates

Router templates capture the overall routing strategy for a task. Pick the template that
aligns with your requirements, then let the router pick the precise provider/model pair.

| Template       | Behavior                                                                          |
|----------------|-----------------------------------------------------------------------------------|
| `code_focused` | Prefers OpenAI quality models for complex coding tasks and long-form reasoning.   |
| `speed_focused`| Routes to Groq-hosted models for the fastest possible completions.                |
| `cost_focused` | Uses local LLMs when available to minimize spending while maintaining reliability.|
| `balanced`     | Smart mix of all providers; balances speed, cost, and quality per request.        |

When calling `LLMRouter.chat`, pass `template="code_focused"` (or any option above) to force
the corresponding routing behavior. If omitted, the router defaults to the balanced strategy.

---

### Persona Modes

Personas define domain-specific tone, temperature, and safety posture. They influence both
prompting and model selection. Use the table below as a quick reference:

| Persona    | Temperature | Safety  | Best LLM |
|------------|-------------|---------|----------|
| Healthcare | 0.3         | High    | Claude   |
| Finance    | 0.2         | High    | GPT-4    |
| Defense    | 0.1         | Maximum | Local    |
| Education  | 0.7         | Medium  | Any      |

To activate a persona, pass `persona="healthcare"` when calling `LLMRouter.chat`. This applies
the appropriate system prompt, temperature clamp, and safety filters.

---

### Combined: Template + Persona

Router templates and personas layer together for optimal routing:

1. **Template** sets the strategic routing bias (speed, cost, quality, or balance).
2. **Persona** constrains tone, safety, and temperature before the prompt is sent.
3. The router evaluates both inputs, then selects the provider/model that satisfies both.

Example:

```python
response = await router.chat(
    "Summarize HIPAA updates for product managers.",
    template="balanced",
    persona="healthcare",
)
```

In this case, the `balanced` template keeps latency and cost in check while the `healthcare`
persona enforces high safety and clinical tone requirements. Adjust both parameters to fit
each task's needs.

---

Keep this guide up to date whenever new templates or personas are added so teams can route
requests confidently.

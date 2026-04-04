# 🎯 Smart Routing Quick Reference

## 🚀 Two Main Commands

### 1. Smart Route (Auto-Choose Best)
```python
openrouter_smart_route(prompt="your question", task="auto")
```

### 2. Cascade (Never Fails!)
```python
openrouter_cascade(prompt="your question")
```

---

## 📋 Task Types

| Task | Routes To | Use For |
|------|-----------|---------|
| `quick` | Groq 8B (0.5s) | Quick queries, status |
| `simple` | Groq 8B (0.5s) | Simple questions |
| `complex` | Groq 70B (2s) | Reasoning, analysis |
| `coding` | Groq 70B (2s) | Code review, generation |
| `offline` | Local Ollama | No internet available |
| `auto` | Brain decides | Let brain choose |

---

## ⚡ Speed Hierarchy

1. **Groq 8B** → 0.5s (500 tok/s) ⚡⚡⚡
2. **Groq 70B** → 2s (500 tok/s) ⚡⚡⚡
3. **Local 3B** → 5s (50 tok/s) ⚡⚡
4. **Local 8B** → 10s (25 tok/s) ⚡

---

## 🔄 Cascade Order

```
Groq Fast → Groq Quality → Local Fast → Local Quality → Cloud Backup
```

---

## 💡 Examples

**Quick status:**
```python
openrouter_smart_route(prompt="Is PR merged?", task="quick")
```

**Code review:**
```python
openrouter_smart_route(prompt="Review code", task="coding")
```

**Never fail:**
```python
openrouter_cascade(prompt="Important task")
```

---

## 🆓 All FREE!

- Groq: FREE (500 tok/s!)
- Ollama: FREE (local)
- Together: FREE ($25 credit)
- OpenRouter: FREE (free tier)

---

**Full docs:** `SMART_ROUTING.md`

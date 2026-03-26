# LLM Configuration Templates

> **Pick a template, copy to `.env`, done!**  
> Each template is pre-configured for a specific use case.  
> No expertise required - sensible defaults that just work.

## Available Templates (March 2026)

| Template | File | Best For | Cost | Privacy |
|----------|------|----------|------|---------|
| 🔒 Privacy First | `llm-privacy-first.env` | Lawyers, doctors, regulated industries | FREE | ⭐⭐⭐⭐⭐ |
| 💰 Budget Zero | `llm-budget-zero.env` | Students, hobbyists, learning | FREE | ⭐⭐⭐⭐ |
| ⚡ Speed Demon | `llm-speed-demon.env` | Real-time apps, high volume | FREE | ⭐⭐⭐⭐ |
| 💼 Business Standard | `llm-business-standard.env` | SMBs, consultants | $20-50/mo | ⭐⭐⭐⭐ |
| 👨‍💻 Developer | `llm-developer.env` | Coding, debugging | $10-30/mo | ⭐⭐⭐⭐ |
| 🌏 Aussie Default | `llm-aussie-default.env` | Joseph's recommended | $0-20/mo | ⭐⭐⭐⭐⭐ |

## Quick Start

1. **Choose your template** based on your needs
2. **Copy to your project**:
   ```bash
   cp templates/llm-aussie-default.env .env
   ```
3. **Add your API keys** (get free keys from providers)
4. **Done!** Your LLM is configured.

## What Each Template Does

### 🔒 Privacy First
- **100% local** - data never leaves your machine
- Works completely offline
- Perfect for sensitive data (medical, legal, financial)
- Requires 8GB+ RAM

### 💰 Budget Zero  
- **$0 forever** - no credit card needed
- Uses Groq and Gemini free tiers
- Falls back to local models
- Great for learning and personal use

### ⚡ Speed Demon
- **Groq first** - fastest inference (300+ tokens/sec)
- Sub-second response times
- Perfect for real-time applications
- Falls back to local if rate limited

### 💼 Business Standard
- **Quality + cost balance**
- Uses free tiers first, paid when needed
- GPT-4o-mini and Haiku for value
- Typical cost: $20-50/month

### 👨‍💻 Developer
- **Optimized for coding tasks**
- GPT-4o and Claude excel at code
- Gemini for reviewing large codebases
- Typical cost: $10-30/month

### 🌏 Aussie Default (Recommended!)
- **Joseph's balanced setup**
- Local first, cloud when needed
- Works offline too
- GST notes for paid providers
- Typical cost: $0-20/month

## Customizing Templates

Templates are starting points. You can:

1. **Change the default model**: Edit `DEFAULT_MODEL=`
2. **Adjust fallback chain**: Edit `FALLBACK_CHAIN=`
3. **Enable/disable cloud**: Set `ALLOW_CLOUD_FALLBACK=`
4. **Go offline**: Set `OFFLINE_MODE=true`

## Model Codes Quick Reference

| Code | Model | Cost |
|------|-------|------|
| L1 | Local llama3.2:3b | FREE |
| L2 | Local llama3.1:8b | FREE |
| GR | Groq llama 70B | FREE |
| GO | Gemini Flash | FREE |
| OP | GPT-4o | Paid |
| OP2 | GPT-4o-mini | Paid |
| CL | Claude Sonnet | Paid |
| CL2 | Claude Haiku | Paid |

See [MODEL_GUIDE.md](../docs/MODEL_GUIDE.md) for complete documentation.

---

*Templates last verified: March 2026*  
*Part of Agentic Brain - Universal AI Assistant*

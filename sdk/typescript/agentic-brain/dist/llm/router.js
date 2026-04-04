"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.LLMRouter = void 0;
const types_1 = require("../types");
class LLMRouter {
    constructor(config = {}) {
        this.mode = config.mode ?? types_1.DeploymentMode.HYBRID;
        this.groqKey = config.groqKey ?? process.env.GROQ_API_KEY;
        this.openaiKey = config.openaiKey ?? process.env.OPENAI_API_KEY;
        this.anthropicKey = config.anthropicKey ?? process.env.ANTHROPIC_API_KEY;
        this.ollamaUrl = config.ollamaUrl ?? 'http://localhost:11434';
    }
    /** Route to the fastest available provider for low-latency responses. */
    async routeFast(prompt) {
        const start = Date.now();
        if (this.groqKey) {
            const content = await this.callGroq(prompt);
            return { provider: 'groq', content, elapsedMs: Date.now() - start };
        }
        if (this.mode !== types_1.DeploymentMode.CLOUD) {
            const content = await this.callOllama(prompt);
            return { provider: 'ollama', content, elapsedMs: Date.now() - start };
        }
        return { provider: 'none', content: '', elapsedMs: Date.now() - start };
    }
    /** Route to highest-quality provider for deep reasoning. */
    async routeDeep(prompt) {
        const start = Date.now();
        if (this.anthropicKey) {
            const content = await this.callAnthropic(prompt);
            return { provider: 'anthropic', content, elapsedMs: Date.now() - start };
        }
        if (this.openaiKey) {
            const content = await this.callOpenAI(prompt);
            return { provider: 'openai', content, elapsedMs: Date.now() - start };
        }
        return this.routeFast(prompt);
    }
    /** Run multiple providers in parallel and return all responses. */
    async routeConsensus(prompt) {
        const providers = [];
        if (this.groqKey)
            providers.push(this.routeFast(prompt));
        if (this.anthropicKey || this.openaiKey)
            providers.push(this.routeDeep(prompt));
        if (this.mode !== types_1.DeploymentMode.CLOUD) {
            providers.push(this.callOllama(prompt).then(content => ({
                provider: 'ollama',
                content,
                elapsedMs: 0,
            })));
        }
        return Promise.all(providers);
    }
    async callGroq(prompt) {
        const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.groqKey}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: 'llama-3.1-8b-instant',
                messages: [{ role: 'user', content: prompt }],
            }),
        });
        const data = await res.json();
        return data.choices[0]?.message?.content ?? '';
    }
    async callAnthropic(prompt) {
        const res = await fetch('https://api.anthropic.com/v1/messages', {
            method: 'POST',
            headers: {
                'x-api-key': this.anthropicKey,
                'anthropic-version': '2023-06-01',
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: 'claude-3-5-sonnet-20241022',
                max_tokens: 1024,
                messages: [{ role: 'user', content: prompt }],
            }),
        });
        const data = await res.json();
        return data.content[0]?.text ?? '';
    }
    async callOpenAI(prompt) {
        const res = await fetch('https://api.openai.com/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.openaiKey}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: 'gpt-4o-mini',
                messages: [{ role: 'user', content: prompt }],
            }),
        });
        const data = await res.json();
        return data.choices[0]?.message?.content ?? '';
    }
    async callOllama(prompt) {
        const res = await fetch(`${this.ollamaUrl}/api/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: 'llama3.2:3b', prompt, stream: false }),
        });
        const data = await res.json();
        return data.response ?? '';
    }
}
exports.LLMRouter = LLMRouter;

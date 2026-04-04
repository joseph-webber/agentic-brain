"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AgenticBrain = void 0;
const types_1 = require("./types");
class AgenticBrain {
    constructor(config = {}) {
        this.mode = config.mode ?? types_1.DeploymentMode.HYBRID;
        this.groqKey = config.groqKey ?? process.env.GROQ_API_KEY;
        this.openaiKey = config.openaiKey ?? process.env.OPENAI_API_KEY;
        this.anthropicKey = config.anthropicKey ?? process.env.ANTHROPIC_API_KEY;
        this.ollamaUrl = config.ollamaUrl ?? 'http://localhost:11434';
    }
    async chat(message, options = {}) {
        const layers = options.layers ?? [types_1.ResponseLayer.INSTANT, types_1.ResponseLayer.DEEP];
        const start = Date.now();
        const response = {
            final: '',
            elapsedMs: 0,
        };
        // Parallel layer execution
        const promises = [];
        if (layers.includes(types_1.ResponseLayer.INSTANT)) {
            promises.push(this.getInstant(message).then(r => { response.instant = r; }));
        }
        if (layers.includes(types_1.ResponseLayer.DEEP)) {
            promises.push(this.getDeep(message).then(r => { response.deep = r; }));
        }
        await Promise.all(promises);
        response.final = response.deep ?? response.instant ?? '';
        response.elapsedMs = Date.now() - start;
        return response;
    }
    async *chatStream(message) {
        // Streaming implementation
    }
    async getInstant(message) {
        if (!this.groqKey)
            return '';
        // Groq API call implementation
        return '';
    }
    async getDeep(message) {
        // Claude/GPT API call implementation
        return '';
    }
}
exports.AgenticBrain = AgenticBrain;

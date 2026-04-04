import { AgenticBrainConfig } from '../types';
export interface RoutedResponse {
    provider: string;
    content: string;
    elapsedMs: number;
}
export declare class LLMRouter {
    private groqKey?;
    private openaiKey?;
    private anthropicKey?;
    private ollamaUrl;
    private mode;
    constructor(config?: AgenticBrainConfig);
    /** Route to the fastest available provider for low-latency responses. */
    routeFast(prompt: string): Promise<RoutedResponse>;
    /** Route to highest-quality provider for deep reasoning. */
    routeDeep(prompt: string): Promise<RoutedResponse>;
    /** Run multiple providers in parallel and return all responses. */
    routeConsensus(prompt: string): Promise<RoutedResponse[]>;
    private callGroq;
    private callAnthropic;
    private callOpenAI;
    private callOllama;
}

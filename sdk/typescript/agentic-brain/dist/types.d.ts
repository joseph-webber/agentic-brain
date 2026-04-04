export declare enum DeploymentMode {
    AIRLOCKED = "airlocked",
    CLOUD = "cloud",
    HYBRID = "hybrid"
}
export declare enum ResponseLayer {
    INSTANT = "instant",
    FAST = "fast",
    DEEP = "deep",
    CONSENSUS = "consensus"
}
export interface LayeredResponse {
    instant?: string;
    fast?: string;
    deep?: string;
    consensus?: string;
    final: string;
    elapsedMs: number;
}
export interface AgenticBrainConfig {
    mode?: DeploymentMode;
    groqKey?: string;
    openaiKey?: string;
    anthropicKey?: string;
    ollamaUrl?: string;
}

import { ResponseLayer, LayeredResponse, AgenticBrainConfig } from './types';
export declare class AgenticBrain {
    private mode;
    private groqKey?;
    private openaiKey?;
    private anthropicKey?;
    private ollamaUrl;
    constructor(config?: AgenticBrainConfig);
    chat(message: string, options?: {
        layers?: ResponseLayer[];
        stream?: boolean;
    }): Promise<LayeredResponse>;
    chatStream(message: string): AsyncGenerator<string>;
    private getInstant;
    private getDeep;
}

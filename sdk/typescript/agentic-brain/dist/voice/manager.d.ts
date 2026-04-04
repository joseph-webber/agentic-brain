export interface VoiceOptions {
    voice?: string;
    rate?: number;
    pitch?: number;
}
export interface TTSProvider {
    name: string;
    speak(text: string, options?: VoiceOptions): Promise<void>;
}
export declare class VoiceManager {
    private provider;
    private defaultOptions;
    constructor(options?: VoiceOptions);
    private detectProvider;
    /** Speak text using the detected TTS provider. */
    speak(text: string, options?: VoiceOptions): Promise<void>;
    /** Return the name of the active TTS provider. */
    get providerName(): string;
    /** List available voices (browser only). */
    getVoices(): SpeechSynthesisVoice[];
}

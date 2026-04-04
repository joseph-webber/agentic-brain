export interface VoiceOptions {
  voice?: string;
  rate?: number;
  pitch?: number;
}

export interface TTSProvider {
  name: string;
  speak(text: string, options?: VoiceOptions): Promise<void>;
}

/** Browser-based Web Speech API TTS provider. */
class WebSpeechProvider implements TTSProvider {
  name = 'web-speech';

  async speak(text: string, options: VoiceOptions = {}): Promise<void> {
    return new Promise((resolve, reject) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = options.rate ?? 1.0;
      utterance.pitch = options.pitch ?? 1.0;

      if (options.voice) {
        const voices = window.speechSynthesis.getVoices();
        const match = voices.find(v => v.name.includes(options.voice!));
        if (match) utterance.voice = match;
      }

      utterance.onend = () => resolve();
      utterance.onerror = (e) => reject(new Error(e.error));
      window.speechSynthesis.speak(utterance);
    });
  }
}

/** macOS system TTS via shell (Node.js only). */
class MacOSTTSProvider implements TTSProvider {
  name = 'macos';

  async speak(text: string, options: VoiceOptions = {}): Promise<void> {
    const { execFile } = await import('child_process');
    const args = [text];
    if (options.voice) args.push('-v', options.voice);
    if (options.rate) args.push('-r', String(options.rate));

    return new Promise((resolve, reject) => {
      execFile('say', args, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }
}

export class VoiceManager {
  private provider: TTSProvider;
  private defaultOptions: VoiceOptions;

  constructor(options: VoiceOptions = {}) {
    this.defaultOptions = options;
    this.provider = this.detectProvider();
  }

  private detectProvider(): TTSProvider {
    // Browser environment
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      return new WebSpeechProvider();
    }
    // Node.js on macOS
    if (process.platform === 'darwin') {
      return new MacOSTTSProvider();
    }
    // Fallback: no-op provider
    return {
      name: 'noop',
      async speak() { /* no audio available */ },
    };
  }

  /** Speak text using the detected TTS provider. */
  async speak(text: string, options: VoiceOptions = {}): Promise<void> {
    return this.provider.speak(text, { ...this.defaultOptions, ...options });
  }

  /** Return the name of the active TTS provider. */
  get providerName(): string {
    return this.provider.name;
  }

  /** List available voices (browser only). */
  getVoices(): SpeechSynthesisVoice[] {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      return window.speechSynthesis.getVoices();
    }
    return [];
  }
}

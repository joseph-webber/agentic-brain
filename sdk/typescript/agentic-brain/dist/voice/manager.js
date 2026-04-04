"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.VoiceManager = void 0;
/** Browser-based Web Speech API TTS provider. */
class WebSpeechProvider {
    constructor() {
        this.name = 'web-speech';
    }
    async speak(text, options = {}) {
        return new Promise((resolve, reject) => {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = options.rate ?? 1.0;
            utterance.pitch = options.pitch ?? 1.0;
            if (options.voice) {
                const voices = window.speechSynthesis.getVoices();
                const match = voices.find(v => v.name.includes(options.voice));
                if (match)
                    utterance.voice = match;
            }
            utterance.onend = () => resolve();
            utterance.onerror = (e) => reject(new Error(e.error));
            window.speechSynthesis.speak(utterance);
        });
    }
}
/** macOS system TTS via shell (Node.js only). */
class MacOSTTSProvider {
    constructor() {
        this.name = 'macos';
    }
    async speak(text, options = {}) {
        const { execFile } = await Promise.resolve().then(() => __importStar(require('child_process')));
        const args = [text];
        if (options.voice)
            args.push('-v', options.voice);
        if (options.rate)
            args.push('-r', String(options.rate));
        return new Promise((resolve, reject) => {
            execFile('say', args, (err) => {
                if (err)
                    reject(err);
                else
                    resolve();
            });
        });
    }
}
class VoiceManager {
    constructor(options = {}) {
        this.defaultOptions = options;
        this.provider = this.detectProvider();
    }
    detectProvider() {
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
            async speak() { },
        };
    }
    /** Speak text using the detected TTS provider. */
    async speak(text, options = {}) {
        return this.provider.speak(text, { ...this.defaultOptions, ...options });
    }
    /** Return the name of the active TTS provider. */
    get providerName() {
        return this.provider.name;
    }
    /** List available voices (browser only). */
    getVoices() {
        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
            return window.speechSynthesis.getVoices();
        }
        return [];
    }
}
exports.VoiceManager = VoiceManager;

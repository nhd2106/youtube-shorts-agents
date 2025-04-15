"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AudioGenerator = void 0;
const path_1 = __importDefault(require("path"));
const fs_1 = __importDefault(require("fs"));
const crypto_1 = __importDefault(require("crypto"));
const openai_1 = require("openai");
const text_to_speech_1 = require("@google-cloud/text-to-speech");
const edge_tts_1 = require("@andresaya/edge-tts");
class AudioGenerator {
    constructor() {
        this.cacheDir = path_1.default.join(process.cwd(), "contents", "cache", "audio");
        fs_1.default.mkdirSync(this.cacheDir, { recursive: true });
        this.openaiClient = null;
        this.googleTTSClient = null;
    }
    initOpenAIClient(apiKey) {
        if (!apiKey) {
            throw new Error("OpenAI API key is required for OpenAI TTS");
        }
        this.openaiClient = new openai_1.OpenAI({ apiKey });
    }
    initGoogleTTSClient() {
        this.googleTTSClient = new text_to_speech_1.TextToSpeechClient();
    }
    getAvailableModels() {
        return AudioGenerator.AVAILABLE_MODELS;
    }
    getCacheKey(script, model, voice) {
        const data = JSON.stringify({ script, model, voice });
        return crypto_1.default.createHash("md5").update(data).digest("hex");
    }
    getCachedAudio(cacheKey) {
        const cachePath = path_1.default.join(this.cacheDir, `${cacheKey}.mp3`);
        return fs_1.default.existsSync(cachePath) ? cachePath : null;
    }
    async generateAudio(script, filename, options = {}) {
        try {
            const { model = "edge", voice, outputDir = path_1.default.join(process.cwd(), "contents", "audio"), apiKeys = {}, returnTiming = false, } = options;
            if (!AudioGenerator.AVAILABLE_MODELS[model]) {
                throw new Error(`Invalid model selected. Available models: ${Object.keys(AudioGenerator.AVAILABLE_MODELS).join(", ")}`);
            }
            const selectedModel = AudioGenerator.AVAILABLE_MODELS[model];
            const selectedVoice = voice || selectedModel.defaultVoice;
            if (!selectedModel.voices.includes(selectedVoice)) {
                throw new Error(`Invalid voice for ${model}. Available voices: ${selectedModel.voices.join(", ")}`);
            }
            const cacheKey = this.getCacheKey(script, model, selectedVoice);
            const cachedPath = this.getCachedAudio(cacheKey);
            if (cachedPath && !returnTiming) {
                console.log("Using cached audio file");
                return cachedPath;
            }
            fs_1.default.mkdirSync(outputDir, { recursive: true });
            const outputPath = path_1.default.join(outputDir, `${filename}.mp3`);
            const cachePath = path_1.default.join(this.cacheDir, `${cacheKey}.mp3`);
            switch (model) {
                case "edge":
                    await this.generateEdgeTTS(script, selectedVoice, outputPath);
                    break;
                case "openai":
                    if (!apiKeys.openai) {
                        throw new Error("OpenAI API key is required for OpenAI TTS");
                    }
                    await this.generateOpenAITTS(script, selectedVoice, outputPath, apiKeys.openai);
                    break;
                case "gtts":
                    await this.generateGoogleTTS(script, selectedVoice, outputPath);
                    break;
                default:
                    throw new Error(`Unsupported TTS model: ${model}`);
            }
            if (!fs_1.default.existsSync(outputPath)) {
                throw new Error("Audio generation failed");
            }
            fs_1.default.copyFileSync(outputPath, cachePath);
            if (returnTiming) {
                const timing = await this.getAudioTiming(script);
                return [outputPath, timing];
            }
            return outputPath;
        }
        catch (error) {
            console.error("Error generating audio:", error);
            throw error;
        }
    }
    async generateEdgeTTS(script, voice, outputPath) {
        try {
            const tts = new edge_tts_1.EdgeTTS();
            const cleanScript = script
                .trim()
                .replace(/[\n\r]+/g, " ")
                .replace(/[<>]/g, "")
                .replace(/&/g, "and");
            if (!cleanScript) {
                throw new Error("Script cannot be empty");
            }
            const basePath = outputPath.replace(/\.mp3$/, "");
            console.log("Starting Edge TTS synthesis...");
            await tts.synthesize(cleanScript, voice, {
                pitch: "0Hz",
                rate: "25%",
                volume: "0%",
            });
            console.log("Saving audio file...");
            await tts.toFile(basePath);
            const finalPath = `${basePath}.mp3`;
            if (!fs_1.default.existsSync(finalPath)) {
                throw new Error(`Failed to generate audio file at ${finalPath}`);
            }
            if (outputPath !== finalPath) {
                fs_1.default.renameSync(finalPath, outputPath);
            }
        }
        catch (error) {
            console.error("EdgeTTS error:", error);
            throw error;
        }
    }
    async generateOpenAITTS(script, voice, outputPath, apiKey) {
        if (!this.openaiClient) {
            this.initOpenAIClient(apiKey);
        }
        const response = await this.openaiClient.audio.speech.create({
            model: "tts-1",
            voice: voice,
            input: script,
            speed: 1.25,
        });
        const buffer = Buffer.from(await response.arrayBuffer());
        fs_1.default.writeFileSync(outputPath, buffer);
    }
    async generateGoogleTTS(script, voice, outputPath) {
        if (!this.googleTTSClient) {
            this.initGoogleTTSClient();
        }
        const request = {
            input: { text: script },
            voice: { languageCode: "vi-VN", name: voice },
            audioConfig: { audioEncoding: "MP3" },
        };
        const response = await this.googleTTSClient.synthesizeSpeech(request);
        const audioContent = response[0].audioContent;
        fs_1.default.writeFileSync(outputPath, audioContent);
    }
    async getAudioTiming(script) {
        const words = script.split(/\s+/);
        const approximateWordDuration = 0.3;
        const segments = [];
        let currentTime = 0;
        for (const word of words) {
            const duration = approximateWordDuration;
            segments.push({
                word,
                start: currentTime,
                end: currentTime + duration,
                duration,
            });
            currentTime += duration;
        }
        return segments;
    }
}
exports.AudioGenerator = AudioGenerator;
AudioGenerator.AVAILABLE_MODELS = {
    edge: {
        name: "Edge TTS",
        defaultVoice: "vi-VN-NamMinhNeural",
        voices: ["vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural"],
    },
    gtts: {
        name: "Google TTS",
        defaultVoice: "vi",
        voices: ["vi"],
    },
    openai: {
        name: "OpenAI TTS",
        defaultVoice: "echo",
        voices: ["echo", "alloy", "fable", "onyx", "nova", "shimmer"],
    },
    elevenlabs: {
        name: "ElevenLabs",
        defaultVoice: "t1LUnfTt7pXaYjubT04d",
        voices: [
            "t1LUnfTt7pXaYjubT04d",
            "WVkYyTxxVgMOsw1IIVL0",
            "7hsfEc7irDn6E8br0qfw",
        ],
    },
};
//# sourceMappingURL=AudioGenerator.js.map
import path from "path";
import fs from "fs";
import crypto from "crypto";
import { OpenAI } from "openai";
import { TTSModels, ApiKeys, AudioSegment } from "../types";
import { TextToSpeechClient } from "@google-cloud/text-to-speech";
import { EdgeTTS } from "@andresaya/edge-tts";

export class AudioGenerator {
  private static readonly AVAILABLE_MODELS: TTSModels = {
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

  private cacheDir: string;
  private openaiClient: OpenAI | null;
  private googleTTSClient: TextToSpeechClient | null;

  constructor() {
    this.cacheDir = path.join(process.cwd(), "contents", "cache", "audio");
    fs.mkdirSync(this.cacheDir, { recursive: true });
    this.openaiClient = null;
    this.googleTTSClient = null;
  }

  private initOpenAIClient(apiKey: string): void {
    if (!apiKey) {
      throw new Error("OpenAI API key is required for OpenAI TTS");
    }
    this.openaiClient = new OpenAI({ apiKey });
  }

  private initGoogleTTSClient(): void {
    this.googleTTSClient = new TextToSpeechClient();
  }

  getAvailableModels(): TTSModels {
    return AudioGenerator.AVAILABLE_MODELS;
  }

  private getCacheKey(script: string, model: string, voice: string): string {
    const data = JSON.stringify({ script, model, voice });
    return crypto.createHash("md5").update(data).digest("hex");
  }

  private getCachedAudio(cacheKey: string): string | null {
    const cachePath = path.join(this.cacheDir, `${cacheKey}.mp3`);
    return fs.existsSync(cachePath) ? cachePath : null;
  }

  async generateAudio(
    script: string,
    filename: string,
    options: {
      model?: string;
      voice?: string;
      outputDir?: string;
      apiKeys?: ApiKeys;
      returnTiming?: boolean;
    } = {}
  ): Promise<string | [string, AudioSegment[]]> {
    try {
      const {
        model = "edge",
        voice,
        outputDir = path.join(process.cwd(), "contents", "audio"),
        apiKeys = {},
        returnTiming = false,
      } = options;

      // Validate model and voice
      if (!AudioGenerator.AVAILABLE_MODELS[model]) {
        throw new Error(
          `Invalid model selected. Available models: ${Object.keys(
            AudioGenerator.AVAILABLE_MODELS
          ).join(", ")}`
        );
      }

      const selectedModel = AudioGenerator.AVAILABLE_MODELS[model];
      const selectedVoice = voice || selectedModel.defaultVoice;

      if (!selectedModel.voices.includes(selectedVoice)) {
        throw new Error(
          `Invalid voice for ${model}. Available voices: ${selectedModel.voices.join(
            ", "
          )}`
        );
      }

      // Check cache
      const cacheKey = this.getCacheKey(script, model, selectedVoice);
      const cachedPath = this.getCachedAudio(cacheKey);

      if (cachedPath && !returnTiming) {
        console.log("Using cached audio file");
        return cachedPath;
      }

      // Create output directory
      fs.mkdirSync(outputDir, { recursive: true });
      const outputPath = path.join(outputDir, `${filename}.mp3`);
      const cachePath = path.join(this.cacheDir, `${cacheKey}.mp3`);

      // Generate audio based on selected model
      switch (model) {
        case "edge":
          await this.generateEdgeTTS(script, selectedVoice, outputPath);
          break;

        case "openai":
          if (!apiKeys.openai) {
            throw new Error("OpenAI API key is required for OpenAI TTS");
          }
          await this.generateOpenAITTS(
            script,
            selectedVoice,
            outputPath,
            apiKeys.openai
          );
          break;

        case "gtts":
          await this.generateGoogleTTS(script, selectedVoice, outputPath);
          break;

        default:
          throw new Error(`Unsupported TTS model: ${model}`);
      }

      // Verify file was generated
      if (!fs.existsSync(outputPath)) {
        throw new Error("Audio generation failed");
      }

      // Cache the generated audio
      fs.copyFileSync(outputPath, cachePath);

      if (returnTiming) {
        const timing = await this.getAudioTiming(script);
        return [outputPath, timing];
      }

      return outputPath;
    } catch (error) {
      console.error("Error generating audio:", error);
      throw error;
    }
  }

  private async generateEdgeTTS(
    script: string,
    voice: string,
    outputPath: string
  ): Promise<void> {
    try {
      const tts = new EdgeTTS();
      // Clean and validate the script
      const cleanScript = script
        .trim()
        .replace(/[\n\r]+/g, " ")
        .replace(/[<>]/g, "")
        .replace(/&/g, "and");

      if (!cleanScript) {
        throw new Error("Script cannot be empty");
      }

      // Remove .mp3 extension if present as the library adds it automatically
      const basePath = outputPath.replace(/\.mp3$/, "");

      console.log("Starting Edge TTS synthesis...");
      await tts.synthesize(cleanScript, voice, {
        pitch: "0Hz",
        rate: "25%",
        volume: "0%",
      });

      console.log("Saving audio file...");
      await tts.toFile(basePath);

      // Verify the file exists with .mp3 extension
      const finalPath = `${basePath}.mp3`;
      if (!fs.existsSync(finalPath)) {
        throw new Error(`Failed to generate audio file at ${finalPath}`);
      }

      // If the original path had no extension, rename the file
      if (outputPath !== finalPath) {
        fs.renameSync(finalPath, outputPath);
      }
    } catch (error) {
      console.error("EdgeTTS error:", error);
      throw error;
    }
  }

  private async generateOpenAITTS(
    script: string,
    voice: string,
    outputPath: string,
    apiKey: string
  ): Promise<void> {
    if (!this.openaiClient) {
      this.initOpenAIClient(apiKey);
    }

    const response = await this.openaiClient!.audio.speech.create({
      model: "tts-1",
      voice: voice as
        | "echo"
        | "alloy"
        | "fable"
        | "onyx"
        | "nova"
        | "shimmer"
        | "ash"
        | "coral"
        | "sage",
      input: script,
      speed: 1.25,
    });

    const buffer = Buffer.from(await response.arrayBuffer());
    fs.writeFileSync(outputPath, buffer);
  }

  private async generateGoogleTTS(
    script: string,
    voice: string,
    outputPath: string
  ): Promise<void> {
    if (!this.googleTTSClient) {
      this.initGoogleTTSClient();
    }

    const request = {
      input: { text: script },
      voice: { languageCode: "vi-VN", name: voice },
      audioConfig: { audioEncoding: "MP3" as const },
    };

    const response = await this.googleTTSClient!.synthesizeSpeech(request);
    const audioContent = response[0].audioContent;
    fs.writeFileSync(outputPath, audioContent as Buffer);
  }

  private async getAudioTiming(script: string): Promise<AudioSegment[]> {
    // This is a placeholder. In a real implementation, you would use
    // a speech recognition service to get precise word timings.
    // For now, we'll create approximate timings based on word count
    const words = script.split(/\s+/);
    const approximateWordDuration = 0.3; // seconds per word
    const segments: AudioSegment[] = [];
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

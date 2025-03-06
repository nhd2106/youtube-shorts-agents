export interface VideoFormat {
  type: "shorts" | "normal";
  duration: string;
  width: number;
  height: number;
  aspectRatio: string;
}

export interface Content {
  title: string;
  script: string;
  hashtags: string[];
  imagePrompts: string[];
  format?: {
    type: string;
  };
  formatDetails?: {
    duration: string;
    width: number;
    height: number;
    aspectRatio: string;
  };
  imageUrls?: string[];
}

export interface RequestData {
  requestId: string;
  status: RequestStatus;
  progress: number;
  result: Record<string, any> | null;
  error: string | null;
  createdAt: number;
  updatedAt: number;
}

export enum RequestStatus {
  PENDING = "pending",
  GENERATING_CONTENT = "generating_content",
  GENERATING_AUDIO = "generating_audio",
  GENERATING_IMAGES = "generating_images",
  WAITING_FOR_IMAGE_SELECTION = "waiting_for_image_selection",
  GENERATING_VIDEO = "generating_video",
  COMPLETED = "completed",
  FAILED = "failed",
}

export interface TTSModel {
  name: string;
  defaultVoice: string;
  voices: string[];
}

export interface TTSModels {
  [key: string]: TTSModel;
}

export interface ImageGenerationOptions {
  prompt: string;
  width: number;
  height: number;
  steps?: number;
  n?: number;
  responseFormat?: string;
}

export interface AudioSegment {
  word: string;
  start: number;
  end: number;
  duration: number;
}

export interface ApiKeys {
  openai?: string;
  elevenlabs?: string;
  together?: string;
}

export interface VideoGenerationResult {
  videoPath: string;
  thumbnailPath: string;
}

export interface VideoGeneratorConfig {
  WIDTH: number;
  HEIGHT: number;
  DURATION: number;
}

export interface VideoGenerator extends VideoGeneratorConfig {
  setFormat(format: string): void;
  generateVideo(options: any): Promise<any>;
  getPreciseWordTimings(audioPath: string, script: string): Promise<any>;
}

export interface AudioGeneratorOptions {
  model?: string;
  voice?: string;
  outputDir?: string;
  apiKeys?: ApiKeys;
  api_keys?: ApiKeys; // Support both formats for backward compatibility
  returnTiming?: boolean;
}

declare module "whisper-node" {
  interface WhisperOptions {
    language?: string;
    word_timestamps?: boolean;
    gen_file_txt?: boolean;
    gen_file_subtitle?: boolean;
    gen_file_vtt?: boolean;
  }

  interface WhisperConfig {
    modelName?: string;
    modelPath?: string;
    whisperOptions?: WhisperOptions;
  }

  interface WhisperWord {
    word: string;
    start: string;
    end: string;
  }

  interface WhisperSegment {
    start: string;
    end: string;
    speech: string;
    words?: WhisperWord[];
  }

  function whisper(
    filePath: string,
    config?: WhisperConfig
  ): Promise<WhisperSegment[]>;

  export = whisper;
}

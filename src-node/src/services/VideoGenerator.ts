import path from "path";
import fs from "fs";
import ffmpeg from "fluent-ffmpeg";
import { VideoFormat } from "../types";
import { OpenAI } from "openai";
import { spawn } from "child_process";
import os from "os";

interface TextClip {
  text: string;
  start: number;
  duration: number;
  isTitle?: boolean;
}

interface TranscriptSegment {
  text: string;
  start: number;
  end: number;
  duration: number;
}

export class VideoGenerator implements VideoGenerator {
  public readonly WIDTH: number = 1080;
  public readonly HEIGHT: number = 1920;
  public readonly DURATION: number = 60;
  private videoFormats: Record<string, VideoFormat>;
  private currentFormat: string | null;
  private width: number | null;
  private height: number | null;
  private duration: number | null;
  private defaultVideoDir: string;
  private defaultThumbnailDir: string;
  private defaultTempDir: string;
  private openaiClient: OpenAI | null;

  constructor() {
    this.videoFormats = {
      shorts: {
        type: "shorts",
        duration: "60s",
        width: 1080,
        height: 1920,
        aspectRatio: "9:16",
      },
      normal: {
        type: "normal",
        duration: "flexible",
        width: 1920,
        height: 1080,
        aspectRatio: "16:9",
      },
    };

    this.currentFormat = "shorts";
    this.width = 1080;
    this.height = 1920;
    this.duration = 60;
    this.openaiClient = null;

    // Set default directories
    const baseDir = process.cwd();
    this.defaultVideoDir = path.join(baseDir, "contents");
    this.defaultThumbnailDir = path.join(baseDir, "contents");
    this.defaultTempDir = path.join(baseDir, "contents", "temp");

    // Create temp directory
    fs.mkdirSync(this.defaultTempDir, { recursive: true });
  }

  private initOpenAIClient(apiKey: string): void {
    if (!apiKey) {
      throw new Error("OpenAI API key is required for prompt generation");
    }
    this.openaiClient = new OpenAI({ apiKey });
  }

  setFormat(formatType: string): void {
    if (!this.videoFormats[formatType]) {
      throw new Error(
        `Invalid format type. Choose from: ${Object.keys(
          this.videoFormats
        ).join(", ")}`
      );
    }

    if (this.currentFormat !== formatType) {
      this.currentFormat = formatType;
      this.width = this.videoFormats[formatType].width;
      this.height = this.videoFormats[formatType].height;
      console.log(
        `Video format set to ${formatType} with dimensions ${this.width}x${this.height}`
      );
    }
  }

  private splitIntoPhrases(text: string): string[] {
    // Split on punctuation but keep the punctuation marks
    const pattern = /([.!?,;:])/;

    // Split text into sentences first
    const sentences = text.split(pattern).filter(Boolean);

    // Clean up and combine punctuation with phrases
    const phrases: string[] = [];
    let currentPhrase = "";

    for (const item of sentences) {
      if (!item.trim()) continue;

      if (pattern.test(item)) {
        // This is punctuation, add it to current phrase
        currentPhrase += item;
        phrases.push(currentPhrase.trim());
        currentPhrase = "";
      } else {
        // This is text, start new phrase
        if (currentPhrase) {
          phrases.push(currentPhrase.trim());
        }
        currentPhrase = item;
      }
    }

    // Add any remaining phrase
    if (currentPhrase) {
      phrases.push(currentPhrase.trim());
    }

    // Filter out empty phrases and normalize whitespace
    return phrases
      .filter((phrase) => phrase.trim())
      .map((phrase) => phrase.replace(/\s+/g, " ").trim());
  }

  async generateVideo(
    audioPath: string,
    content: {
      title: string;
      script: string;
    },
    requestId: string,
    backgroundImages: string[],
    progressCallback?: (progress: number) => void
  ): Promise<{ videoPath: string; thumbnailPath: string; scriptPath: string }> {
    try {
      // Set audio duration
      this.duration = await this.getAudioDuration(audioPath);
      if (!this.duration) {
        throw new Error("Could not determine audio duration");
      }

      // Validate background images
      if (
        !backgroundImages ||
        !Array.isArray(backgroundImages) ||
        backgroundImages.length === 0
      ) {
        throw new Error("No background images provided");
      }

      // Set output paths using request-specific directories
      const requestDir = path.join(process.cwd(), "contents", requestId);
      const videoDir = path.join(requestDir, "video");
      const scriptDir = path.join(requestDir, "script");

      // Create necessary directories with explicit permissions
      await fs.promises.mkdir(requestDir, { recursive: true, mode: 0o755 });
      await fs.promises.mkdir(videoDir, { recursive: true, mode: 0o755 });
      await fs.promises.mkdir(scriptDir, { recursive: true, mode: 0o755 });

      const videoPath = path.join(videoDir, `${requestId}.mp4`);
      const thumbnailPath = path.join(videoDir, `${requestId}_thumbnail.jpg`);
      const scriptPath = path.join(scriptDir, `${requestId}.txt`);

      // Create video segments from background images
      const segments = await this.createVideoSegments(backgroundImages);

      // Generate optimized transcript from audio and original script
      let transcriptText = content.script;
      let transcriptSegments: TranscriptSegment[] = [];
      try {
        const transcriptResult = await this.generateAudioTranscript(audioPath);
        if (transcriptResult && transcriptResult.segments) {
          transcriptSegments = transcriptResult.segments.map(
            (segment: any) => ({
              text: segment.text.trim(),
              start: segment.start,
              end: segment.end,
              duration: segment.end - segment.start,
            })
          );
          transcriptText = transcriptResult.text;
        }
      } catch (error) {
        console.warn("Using original script as fallback:", error.message);
        transcriptSegments = this.splitIntoPhrases(transcriptText).map(
          (phrase, index, array) => {
            const segmentDuration = this.duration! / array.length;
            return {
              text: phrase,
              start: index * segmentDuration,
              end: (index + 1) * segmentDuration,
              duration: segmentDuration,
            };
          }
        );
      }

      // Save the script
      await fs.promises.writeFile(scriptPath, transcriptText);

      // Create text clips (title and captions)
      const textClips: TextClip[] = [];

      // Add title clip with fade in/out
      const titleDuration = this.duration;
      textClips.push({
        text: content.title,
        start: 0,
        duration: titleDuration,
        isTitle: true,
      });

      // Add subtitle clips with timing from transcript
      textClips.push(
        ...transcriptSegments.map((segment: TranscriptSegment) => ({
          text: segment.text,
          start: segment.start,
          duration: segment.duration,
          isTitle: false,
        }))
      );

      // Generate final video with text overlays
      await this.renderFinalVideo(
        segments,
        textClips,
        audioPath,
        videoPath,
        progressCallback
      );

      // Generate thumbnail
      await this.generateThumbnail(videoPath, thumbnailPath);

      // Clean up temporary segment files
      for (const segment of segments) {
        try {
          if (fs.existsSync(segment)) {
            await fs.promises.unlink(segment);
          }
        } catch (error) {
          console.warn(`Failed to clean up segment: ${segment}`, error);
        }
      }

      return {
        videoPath,
        thumbnailPath,
        scriptPath,
      };
    } catch (error) {
      console.error("Error generating video:", error);
      throw error;
    }
  }

  private getAudioDuration(audioPath: string): Promise<number> {
    return new Promise((resolve, reject) => {
      ffmpeg.ffprobe(audioPath, (err, metadata) => {
        if (err) reject(err);
        else resolve(metadata.format.duration || 0);
      });
    });
  }

  private async createVideoSegments(
    backgroundImages: string[]
  ): Promise<string[]> {
    if (!this.width || !this.height || !this.duration || !this.currentFormat) {
      throw new Error(
        "Video dimensions, duration, and format must be set first"
      );
    }

    // Validate input images first
    const validImages = backgroundImages.filter((img) => fs.existsSync(img));
    if (validImages.length === 0) {
      throw new Error("No valid background images found");
    }

    // Create temp directory with explicit permissions
    const tempDir = path.join(
      process.cwd(),
      "contents",
      "temp",
      `segments_${Date.now()}`
    );
    try {
      fs.mkdirSync(tempDir, { recursive: true, mode: 0o755 });
    } catch (error) {
      console.error("Error creating temp directory:", error);
      throw new Error(`Failed to create temp directory: ${error.message}`);
    }

    const segmentDuration = this.duration / validImages.length;
    const segments: string[] = [];

    try {
      // Process each image sequentially
      for (let i = 0; i < validImages.length; i++) {
        const imagePath = validImages[i];
        const outputPath = path.join(tempDir, `segment_${i}.mp4`);

        // Calculate zoom and pan parameters with smoother motion
        const zoomStart = 1.0;
        const zoomEnd = 1.05; // Reduced zoom for smoother motion
        const panX = Math.random() * 60 - 30; // Reduced pan range
        const panY = Math.random() * 60 - 30; // Reduced pan range

        // Create the filter complex string with improved transitions
        const filterComplex = [
          // Initial scale and padding
          `scale=${this.width}:${this.height}:force_original_aspect_ratio=increase`,
          `crop=${this.width}:${this.height}`,

          // Improved zoompan with smoother motion
          `zoompan=z='if(lte(zoom,${zoomStart}),${zoomStart},min(zoom+0.0005,${zoomEnd}))':` +
            `x='iw/2-(iw/zoom/2)+(${panX}*sin(on/${Math.ceil(
              segmentDuration * 30
            )}/PI))':` +
            `y='ih/2-(ih/zoom/2)+(${panY}*sin(on/${Math.ceil(
              segmentDuration * 30
            )}/PI))':` +
            `d=${Math.ceil(segmentDuration * 30)}:s=${this.width}x${
              this.height
            }:fps=30`,

          // Improved fade transitions
          `fade=t=in:st=0:d=0.5,fade=t=out:st=${segmentDuration - 0.5}:d=0.5`,
        ].join(",");

        // Create the segment with improved encoding settings
        await new Promise<void>((resolve, reject) => {
          const command = ffmpeg()
            .input(imagePath)
            .inputOptions(["-loop 1"])
            .outputOptions([
              `-t ${segmentDuration}`,
              "-pix_fmt yuv420p",
              "-r 30",
              "-c:v libx264",
              "-preset veryfast", // Better balance of speed and quality
              "-profile:v high",
              "-level 4.2",
              "-crf 23", // Better quality
              "-maxrate 5M",
              "-bufsize 10M",
              "-movflags +faststart",
              "-y",
            ])
            .complexFilter(filterComplex)
            .output(outputPath);

          command.on("start", (cmdline) => {
            console.log(`Starting segment ${i} creation:`, cmdline);
          });

          command.on("stderr", (stderrLine) => {
            console.log(`Segment ${i} progress:`, stderrLine);
          });

          command.on("end", () => {
            if (fs.existsSync(outputPath)) {
              console.log(`Successfully created segment ${i}`);
              segments.push(outputPath);
              resolve();
            } else {
              reject(
                new Error(
                  `Failed to create segment ${i}: Output file not found`
                )
              );
            }
          });

          command.on("error", (err) => {
            console.error(`Error creating segment ${i}:`, err);
            reject(err);
          });

          command.run();
        });

        // Verify the segment was created successfully
        if (!fs.existsSync(segments[segments.length - 1])) {
          throw new Error(`Segment ${i} was not created successfully`);
        }
      }

      return segments;
    } catch (error) {
      // Clean up on error
      segments.forEach((segment) => {
        try {
          if (fs.existsSync(segment)) fs.unlinkSync(segment);
        } catch (e) {
          console.warn(`Failed to clean up segment: ${segment}`, e);
        }
      });

      try {
        if (fs.existsSync(tempDir)) {
          fs.rmSync(tempDir, { recursive: true, force: true });
        }
      } catch (e) {
        console.warn("Failed to clean up temp directory:", e);
      }

      throw error;
    }
  }

  private async renderFinalVideo(
    segments: string[],
    textClips: TextClip[],
    audioPath: string,
    outputPath: string,
    progressCallback?: (progress: number) => void
  ): Promise<void> {
    try {
      // Convert all paths to absolute and normalize them
      outputPath = path.resolve(outputPath);
      audioPath = path.resolve(audioPath);
      segments = segments.map((s) => path.resolve(s));

      console.log(
        `Processing video with ${segments.length} segments and ${textClips.length} text clips`
      );
      console.log(`Output path: ${outputPath}`);
      console.log(`Audio path: ${audioPath}`);

      // Create output directory
      const outputDir = path.dirname(outputPath);
      await fs.promises.mkdir(outputDir, { recursive: true, mode: 0o755 });

      // Create a temp directory in the OS temp directory
      const tempDir = path.join(os.tmpdir(), `ffmpeg_${Date.now()}`);
      await fs.promises.mkdir(tempDir, { recursive: true, mode: 0o755 });
      console.log(`Created temp directory: ${tempDir}`);

      try {
        // STEP 1: First concatenate all video segments without any text
        const concatFilePath = path.join(tempDir, "concat.txt");
        const concatContent = segments
          .map((segment) => `file '${segment.replace(/'/g, "'\\''")}'`)
          .join("\n");
        await fs.promises.writeFile(concatFilePath, concatContent);
        console.log(`Created concat file at ${concatFilePath}`);

        // STEP 2: Concatenate videos and add audio in one step (no text yet)
        const baseVideoPath = path.join(tempDir, "base.mp4");

        await new Promise<void>((resolve, reject) => {
          const command = ffmpeg()
            .input(concatFilePath)
            .inputOptions(["-f", "concat", "-safe", "0"])
            .input(audioPath)
            .outputOptions([
              "-map",
              "0:v", // Use video from first input (concat)
              "-map",
              "1:a", // Use audio from second input
              "-c:v",
              "libx264",
              "-preset",
              "ultrafast",
              "-crf",
              "23",
              "-c:a",
              "aac",
              "-shortest",
              "-pix_fmt",
              "yuv420p",
              "-vf",
              "scale=w=" + this.WIDTH + ":h=" + this.HEIGHT,
            ])
            .output(baseVideoPath)
            .on("start", () => {
              // console.log(`FFmpeg base command: ${cmdline}`);
            })
            .on("stderr", () => {
              // console.log(`FFmpeg base stderr: ${stderrLine}`);
            })
            .on("end", () => resolve())
            .on("error", (err) => {
              console.error("FFmpeg base error:", err);
              reject(err);
            });

          command.run();
        });

        // STEP 3: Add text clips one by one using subtitle filter instead of drawtext
        let currentVideoPath = baseVideoPath;

        // Process title first if it exists
        const titleClip = textClips.find((clip) => clip.isTitle);

        if (titleClip) {
          const withTitlePath = path.join(tempDir, "with_title.mp4");

          // Create a temporary subtitle file for the title
          const titleSubPath = path.join(tempDir, "title.ass");

          // Create an ASS subtitle file with explicit positioning
          // ASS format gives more control over positioning than SRT
          const assHeader = `[Script Info]
ScriptType: v4.00+
PlayResX: ${this.WIDTH}
PlayResY: ${this.HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,Arial,64,&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,1,8,0,0,${Math.floor(
            this.HEIGHT / 4
          )},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`;

          const startTime = this.formatAssTime(titleClip.start);
          const endTime = this.formatAssTime(
            titleClip.start + titleClip.duration
          );
          // Use a smaller max chars per line for title due to larger font size
          const titleText = this.wrapText(titleClip.text, 15); // Shorter lines for title

          const assContent = `${assHeader}Dialogue: 0,${startTime},${endTime},Title,,0,0,0,,${titleText.replace(
            /\n/g,
            "\\N"
          )}`;
          await fs.promises.writeFile(titleSubPath, assContent);

          await new Promise<void>((resolve, reject) => {
            const command = ffmpeg()
              .input(currentVideoPath)
              .outputOptions([
                // Using ASS subtitles for precise positioning
                "-vf",
                `ass=${titleSubPath}`,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                "-c:a",
                "copy",
              ])
              .output(withTitlePath)
              .on("start", () => {
                // console.log(`FFmpeg title command: ${cmdline}`);
              })
              .on("stderr", () => {
                // console.log(`FFmpeg title stderr: ${stderrLine}`);
              })
              .on("end", () => {
                currentVideoPath = withTitlePath;
                resolve();
              })
              .on("error", (err) => {
                console.error("FFmpeg title error:", err);
                reject(err);
              });

            command.run();
          });
        }

        // Process subtitles
        const subtitleClips = textClips.filter((clip) => !clip.isTitle);

        if (subtitleClips.length > 0) {
          // Create a single SRT file for all subtitles
          const subtitlePath = path.join(tempDir, "subtitles.srt");
          let srtContent = "";

          subtitleClips.forEach((clip, index) => {
            const startTime = this.formatSrtTime(clip.start);
            const endTime = this.formatSrtTime(clip.start + clip.duration);
            const subtitleText = this.wrapText(clip.text, 25); // Slightly longer lines for subtitles

            srtContent += `${
              index + 1
            }\n${startTime} --> ${endTime}\n${subtitleText}\n\n`;
          });

          await fs.promises.writeFile(subtitlePath, srtContent);

          const finalVideoPath = path.join(tempDir, "final.mp4");

          await new Promise<void>((resolve, reject) => {
            const command = ffmpeg()
              .input(currentVideoPath)
              .outputOptions([
                // Keep font size at 10 and ensure yellow color
                // In ASS format, yellow is &H0000FFFF (AABBGGRR format)
                "-vf",
                `subtitles=${subtitlePath}:force_style='FontName=Arial,FontSize=10,PrimaryColour=&H0000FFFF,BackColour=&H80000000,BorderStyle=4,Outline=1,Shadow=0,MarginV=30,Alignment=2'`,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                "-c:a",
                "copy",
              ])
              .output(finalVideoPath)
              .on("start", () => {
                // console.log(`FFmpeg subtitles command: ${cmdline}`);
              })
              .on("stderr", () => {
                // console.log(`FFmpeg subtitles stderr: ${stderrLine}`);
              })
              .on("end", () => {
                currentVideoPath = finalVideoPath;
                resolve();
              })
              .on("error", (err) => {
                // console.error("FFmpeg subtitles error:", err);
                reject(err);
              });

            command.run();
          });
        }

        // STEP 5: Move the final video to the output path
        await fs.promises.copyFile(currentVideoPath, outputPath);
        console.log(`Final video saved to ${outputPath}`);

        // Call progress callback with 100% completion
        if (progressCallback) {
          progressCallback(100);
        }
      } finally {
        // Clean up temp directory
        try {
          await fs.promises.rm(tempDir, { recursive: true, force: true });
          console.log(`Cleaned up temp directory: ${tempDir}`);
        } catch (error) {
          console.error(`Error cleaning up temp directory: ${error}`);
        }
      }
    } catch (error) {
      console.error("Error in renderFinalVideo:", error);
      throw error;
    }
  }

  private wrapText(text: string, maxCharsPerLine: number): string {
    // Split text into words
    const words = text.split(" ");
    const lines: string[] = [];
    let currentLine = "";

    // Process each word
    for (let i = 0; i < words.length; i++) {
      const word = words[i];

      // For very long words, split them
      if (word.length > maxCharsPerLine) {
        // If there's already content in the current line, push it first
        if (currentLine.length > 0) {
          lines.push(currentLine);
          currentLine = "";
        }

        // Split the long word into chunks
        let remainingWord = word;
        while (remainingWord.length > 0) {
          const chunkSize = Math.min(maxCharsPerLine - 1, remainingWord.length);
          const chunk =
            remainingWord.substring(0, chunkSize) +
            (remainingWord.length > chunkSize ? "-" : "");
          lines.push(chunk);
          remainingWord = remainingWord.substring(chunkSize);
        }
        continue;
      }

      // If adding this word would exceed max chars, start a new line
      if (
        currentLine.length + word.length + 1 > maxCharsPerLine &&
        currentLine.length > 0
      ) {
        lines.push(currentLine);
        currentLine = word;
      } else {
        // Add word to current line (with space if not first word)
        currentLine =
          currentLine.length === 0 ? word : `${currentLine} ${word}`;
      }
    }

    // Add the last line if it's not empty
    if (currentLine.length > 0) {
      lines.push(currentLine);
    }

    // Join lines with a space instead of FFmpeg newline character
    // We'll handle multi-line text differently
    return lines.join(" ");
  }

  private generateThumbnail(
    videoPath: string,
    thumbnailPath: string
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      ffmpeg(videoPath)
        .screenshots({
          timestamps: ["00:00:01"],
          filename: path.basename(thumbnailPath),
          folder: path.dirname(thumbnailPath),
          size: `${this.width}x${this.height}`,
        })
        .on("end", () => resolve())
        .on("error", (err: Error) => reject(err));
    });
  }

  async generatePromptsWithOpenAI(
    script: string,
    apiKeys: Record<string, string>
  ): Promise<string[] | any> {
    try {
      if (!apiKeys.openai) {
        throw new Error("OpenAI API key is required for prompt generation");
      }

      if (!this.currentFormat) {
        throw new Error("Video format must be set before generating prompts");
      }

      this.initOpenAIClient(apiKeys.openai);
      const response = await this.openaiClient!.chat.completions.create({
        model: "gpt-4o-mini",
        messages: [
          {
            role: "assistant",
            content: this.getPromptGenerationSystemMessage(),
          },
          {
            role: "user",
            content: `Generate ${
              this.currentFormat ?? "shorts" === "shorts" ? "9" : "18"
            } image prompts for this script: ${script}`,
          },
        ],
        temperature: 0.7,
      });
      console.log(response.choices[0].message);

      const content = response.choices[0].message.content;
      if (!content) {
        throw new Error("No prompts generated");
      }

      // Parse prompts from response
      const prompts = content
        .split("\n")
        .map((line) => line.trim())
        // Extract prompts from numbered list format
        .map((line) => {
          // Remove numbered list format (e.g., "1. ", "2. ")
          const withoutNumber = line.replace(/^\d+\.\s*/, "");
          // Remove bold formatting if present
          const withoutFormatting = withoutNumber.replace(/\*\*/g, "");
          return withoutFormatting.trim();
        })
        .filter(
          (line) =>
            line.length > 0 && !line.startsWith("#") && !line.match(/^\s*$/) // Remove empty lines
        );

      console.log(
        `Generated ${prompts.length} prompts for ${this.currentFormat} format`
      );
      return prompts;
    } catch (error) {
      console.error("Error generating prompts:", error);
      console.warn("Using default prompts as fallback");
      // return this.getDefaultPrompts();
    }
  }

  private getPromptGenerationSystemMessage(): string {
    return `You are a professional cinematographer creating video prompts.
Create prompts for image generation that are:
1. Cinematic and photorealistic
2. Include camera angles and cinematography techniques
3. Use specific technical terms (aperture, shutter speed, focal length)
4. Include lighting and atmosphere descriptions
5. Keep each prompt under 500 characters
6. Focus on visual elements that support the script

Example good prompts:
"Low angle shot of city skyline, golden hour lighting, lens flare, dramatic clouds"
"Close up portrait, shallow depth of field, natural window lighting, office setting"
"Wide angle tracking shot, diffused industrial lighting, steady cam movement"`;
  }

  async generateAudioTranscript(
    audioPath: string,
    language: string = "vi"
  ): Promise<any> {
    try {
      if (!fs.existsSync(audioPath)) {
        throw new Error(`Audio file not found at path: ${audioPath}`);
      }

      // Path to the Python script and virtual environment
      const scriptPath = path.join(__dirname, "whisper_transcribe.py");
      const venvPath = path.join(__dirname, "venv");
      const venvPythonPath = path.join(venvPath, "bin", "python3");
      const venvSitePackages = path.join(
        venvPath,
        "lib",
        "python3.11",
        "site-packages"
      );

      // Check if Python script exists
      if (!fs.existsSync(scriptPath)) {
        throw new Error("Whisper transcription script not found");
      }

      // Check if virtual environment exists
      if (!fs.existsSync(venvPythonPath)) {
        throw new Error(
          "Python virtual environment not found. Please run setup_whisper.sh first"
        );
      }

      console.log(`Transcribing audio file: ${audioPath}`);

      // Run Python script using the virtual environment
      return new Promise((resolve) => {
        const env = {
          ...process.env,
          PYTHONPATH: venvSitePackages,
          PATH: `${path.join(venvPath, "bin")}:${process.env.PATH}`,
        };

        const pythonProcess = spawn(
          venvPythonPath,
          [scriptPath, audioPath, language],
          {
            env,
          }
        );

        let outputData = "";
        let errorData = "";

        pythonProcess.stdout.on("data", (data) => {
          outputData += data.toString();
        });

        pythonProcess.stderr.on("data", (data) => {
          errorData += data.toString();
          // Only log stderr if it's not the device info message
          if (!data.toString().includes("Using device:")) {
            console.warn(`Python stderr: ${data}`);
          }
        });

        pythonProcess.on("close", (code) => {
          if (code !== 0) {
            console.error(`Python process exited with code ${code}`);
            console.error("Error output:", errorData);
            // Return empty result instead of rejecting to allow video generation to continue
            resolve({
              text: "",
              segments: [],
            });
            return;
          }

          try {
            const result = JSON.parse(outputData);
            if (result.error) {
              console.error("Transcription error:", result.error);
              resolve({
                text: "",
                segments: [],
              });
              return;
            }
            resolve(result);
          } catch (e) {
            console.error("Failed to parse transcription result:", e);
            resolve({
              text: "",
              segments: [],
            });
          }
        });

        pythonProcess.on("error", (err) => {
          console.error("Failed to start Python process:", err);
          resolve({
            text: "",
            segments: [],
          });
        });
      });
    } catch (error) {
      console.error("Error generating audio transcript:", error);
      return {
        text: "",
        segments: [],
      };
    }
  }

  async generateOptimizedTranscript(
    audioPath: string,
    originalScript?: string,
    language: string = "en"
  ): Promise<string> {
    try {
      // Get the audio transcript using local Whisper
      const transcriptResult = await this.generateAudioTranscript(
        audioPath,
        language
      );
      const audioTranscript = transcriptResult.text;

      // If we have an original script, use it as a reference
      if (originalScript) {
        // For now, just use the original script as it's likely more accurate
        // You could implement more sophisticated text alignment here if needed
        return originalScript;
      }

      // If no original script, return the Whisper transcript
      return audioTranscript;
    } catch (error) {
      console.error("Error generating optimized transcript:", error);
      // If we have an original script, fall back to that
      if (originalScript) {
        console.warn("Falling back to original script");
        return originalScript;
      }
      throw error;
    }
  }

  public async getPreciseWordTimings(
    audioPath: string,
    script: string
  ): Promise<any> {
    try {
      // Use Whisper to get word-level timings
      const transcriptResult = await this.generateAudioTranscript(audioPath);

      if (transcriptResult.segments && transcriptResult.segments.length > 0) {
        // Flatten all words from all segments
        const wordTimings = transcriptResult.segments.flatMap((segment: any) =>
          segment.words
            ? segment.words.map((word: any) => ({
                word: word.text,
                start: word.start,
                end: word.end,
              }))
            : []
        );

        return wordTimings;
      } else {
        // Fallback to simple timing if no word-level data
        return this.getSimpleWordTimings(audioPath, script);
      }
    } catch (error) {
      console.error("Error getting word timings:", error);
      // Fallback to simple timing method
      return this.getSimpleWordTimings(audioPath, script);
    }
  }

  private async getSimpleWordTimings(
    audioPath: string,
    script: string
  ): Promise<any> {
    // Use ffmpeg to analyze audio and get word timings
    const audioAnalysis = await this.analyzeAudio(audioPath);

    // Split script into words
    const words = script.split(/\s+/);

    // Calculate approximate timing for each word based on audio duration
    const audioDuration = audioAnalysis.duration;
    const avgWordDuration = audioDuration / words.length;

    // Generate word timings
    return words.map((word, index) => ({
      word,
      start: index * avgWordDuration,
      end: (index + 1) * avgWordDuration,
    }));
  }

  private async analyzeAudio(audioPath: string): Promise<{ duration: number }> {
    // Use ffprobe to get audio duration
    const ffprobe = require("ffprobe");
    const ffprobeStatic = require("ffprobe-static");

    const { streams } = await ffprobe(audioPath, { path: ffprobeStatic.path });
    const audioStream = streams.find(
      (s: { codec_type: string }) => s.codec_type === "audio"
    );

    return {
      duration: audioStream ? parseFloat(audioStream.duration) : 0,
    };
  }

  // Helper method to format time for SRT files
  private formatSrtTime(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);

    return `${hours.toString().padStart(2, "0")}:${minutes
      .toString()
      .padStart(2, "0")}:${secs.toString().padStart(2, "0")},${ms
      .toString()
      .padStart(3, "0")}`;
  }

  // Helper method to format time for ASS files (different format than SRT)
  private formatAssTime(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const centisecs = Math.floor((seconds % 1) * 100);

    return `${hours.toString().padStart(1, "0")}:${minutes
      .toString()
      .padStart(2, "0")}:${secs.toString().padStart(2, "0")}.${centisecs
      .toString()
      .padStart(2, "0")}`;
  }
}

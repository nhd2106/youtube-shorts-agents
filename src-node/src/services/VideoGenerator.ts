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
  effect?: TextEffect;
}

interface TextEffect {
  name: string;
  style: string;
  animationParams: Record<string, any>;
  fontColor: string;
  backgroundColor?: string;
  fontName?: string;
  stroke?: boolean;
  strokeColor?: string;
  isBold?: boolean;
  fontSize?: number;
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
  private defaultTempDir: string;
  private openaiClient: OpenAI | null;
  private textEffects: TextEffect[] = [
    {
      name: "Pop-in Word by Word",
      style: "bold",
      animationParams: { scale: "1.2", fade: "0.3" },
      fontColor: "white",
      stroke: true,
      strokeColor: "black",
      backgroundColor: "black@0.5",
      isBold: true,
      fontSize: 52,
    },
    {
      name: "Typewriter Effect",
      style: "monospace",
      animationParams: { typingSpeed: "0.1", cursor: true },
      fontColor: "white",
      backgroundColor: "black@0.7",
      fontName: "Courier New",
      isBold: true,
      fontSize: 48,
    },
    {
      name: "Bouncy Word Effect",
      style: "rounded",
      animationParams: { bounce: "0.2", drop: true },
      fontColor: "white",
      backgroundColor: "pink@0.4",
    },
    {
      name: "Wave Motion",
      style: "kinetic",
      animationParams: { amplitude: "5", frequency: "2" },
      fontColor: "#00FFFF",
      stroke: true,
      strokeColor: "#FF00FF",
    },
    {
      name: "Glitchy Text",
      style: "glitch",
      animationParams: { flickerRate: "0.1", displacement: "3" },
      fontColor: "#FF0000",
      backgroundColor: "black@0.7",
    },
    {
      name: "Sliding Subtitles",
      style: "slide",
      animationParams: { direction: "left", speed: "0.2" },
      fontColor: "white",
      stroke: true,
      strokeColor: "black",
    },
    {
      name: "Shake Effect",
      style: "shake",
      animationParams: { intensity: "2", randomness: "0.5" },
      fontColor: "#FFFF00",
      stroke: true,
      strokeColor: "black",
    },
    {
      name: "Expanding Words",
      style: "expand",
      animationParams: { startScale: "0.5", endScale: "1.2" },
      fontColor: "white",
      backgroundColor: "black@0.5",
    },
    {
      name: "3D Rotation Effect",
      style: "3d",
      animationParams: { angle: "15", perspective: "100" },
      fontColor: "#00FFFF",
      stroke: true,
      strokeColor: "#000080",
    },
    {
      name: "Handwritten Scribble Text",
      style: "handwritten",
      animationParams: { revealSpeed: "0.1", jitter: "2" },
      fontColor: "#333333",
      backgroundColor: "white@0.3",
      fontName: "Comic Sans MS",
    },
  ];

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
      // console.log(
      //   `Video format set to ${formatType} with dimensions ${this.width}x${this.height}`
      // );
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
      language?: string;
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

      // Determine the language - default to Vietnamese if not specified
      const language = content.language || "vi";
      console.log(`Using language: ${language} for subtitles`);

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
        const transcriptResult = await this.generateAudioTranscript(
          audioPath,
          language
        );
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
        console.warn(
          `Using original script as fallback (language: ${language}):`,
          error.message
        );
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

      // Apply text effects to subtitle clips
      const textClipsWithEffects = this.applyTextEffects(textClips);

      // Generate final video with text overlays
      await this.renderFinalVideo(
        segments,
        textClipsWithEffects,
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

          command.on("start", () => {
            // console.log(`Starting segment ${i} creation:`, cmdline);
          });

          command.on("stderr", () => {
            // console.log(`Segment ${i} progress:`, stderrLine);
          });

          command.on("end", () => {
            if (fs.existsSync(outputPath)) {
              // console.log(`Successfully created segment ${i}`);
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
            .on("start", (cmdline) => {
              console.log(`FFmpeg base command: ${cmdline}`);
            })
            .on("stderr", (stderrLine) => {
              // console.log(`FFmpeg base stderr: ${stderrLine}`);
            })
            .on("end", () => resolve())
            .on("error", (err) => {
              console.error("FFmpeg base error:", err);
              reject(err);
            });

          command.run();
        });

        // STEP 3: Add text clips one by one
        let currentVideoPath = baseVideoPath;

        // Process title first if it exists
        const titleClip = textClips.find((clip) => clip.isTitle);

        if (titleClip) {
          const withTitlePath = path.join(tempDir, "with_title.mp4");

          await new Promise<void>((resolve, reject) => {
            // Create drawtext filter for title with proper text width constraints
            const titleFontSize = 50;
            // Implement text breaking by adding newlines for long titles
            let formattedTitle = titleClip.text;

            // Limit width by adding newlines if title is too long
            if (formattedTitle.length > 30) {
              const words = formattedTitle.split(" ");
              let currentLine = "";
              formattedTitle = "";

              words.forEach((word) => {
                if ((currentLine + " " + word).length > 30) {
                  formattedTitle += currentLine + "\\n";
                  currentLine = word;
                } else {
                  currentLine = currentLine ? currentLine + " " + word : word;
                }
              });

              if (currentLine) {
                formattedTitle += currentLine;
              }
            }

            const drawTextFilters = `drawtext=text='${formattedTitle
              .replace(/\\/g, "\\\\")
              .replace(/'/g, "\\\\'")
              .replace(
                /:/g,
                "\\:"
              )}':fontsize=${titleFontSize}:fontcolor=yellow:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,${
              titleClip.start
            },${titleClip.start + titleClip.duration})'`;

            const command = ffmpeg()
              .input(currentVideoPath)
              .outputOptions([
                "-vf",
                drawTextFilters,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "28",
                "-c:a",
                "copy",
              ])
              .output(withTitlePath)
              .on("start", (commandLine) => {
                console.log("FFmpeg title command:", commandLine);
              })
              .on("end", () => {
                console.log(`Added title to video: ${withTitlePath}`);
                currentVideoPath = withTitlePath;
                resolve();
              })
              .on("error", (err) => {
                console.error("Error adding title to video:", err);
                reject(err);
              });

            command.run();
          });
        }

        // Process subtitles with effects
        const subtitleClips = textClips.filter((clip) => !clip.isTitle);

        if (subtitleClips.length > 0) {
          // First try using the ASS format for advanced styling
          try {
            // Create an ASS subtitle file
            const assSubtitlePath = path.join(tempDir, "subtitles.ass");

            // Generate ASS subtitles content
            await this.generateASSSubtitles(
              subtitleClips,
              assSubtitlePath,
              this.WIDTH,
              this.HEIGHT
            );
            console.log(`Created ASS subtitle file at ${assSubtitlePath}`);

            const assVideoPath = path.join(tempDir, "with_ass_subtitles.mp4");

            // Properly escape the subtitle path
            const escapedSubtitlePath = path
              .resolve(assSubtitlePath)
              .replace(/\\/g, "/");
            console.log(`Using subtitle path: ${escapedSubtitlePath}`);

            try {
              await new Promise<void>((resolve, reject) => {
                // Ensure the subtitle path is properly escaped for ffmpeg
                const assSubtitlePathEscaped = escapedSubtitlePath.replace(
                  /([\\'])/g,
                  "\\$1"
                );
                console.log(
                  `Using full subtitle path (escaped): ${assSubtitlePathEscaped}`
                );

                // Create a simplified filter with proper escaping
                const subtitleFilter = `subtitles='${assSubtitlePathEscaped}'`;
                console.log(`Subtitle filter: ${subtitleFilter}`);

                const command = ffmpeg()
                  .input(currentVideoPath)
                  .outputOptions([
                    // Use subtitles filter with ASS format
                    "-vf",
                    subtitleFilter,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "23",
                    "-c:a",
                    "copy",
                  ])
                  .output(assVideoPath)
                  .on("start", (cmdline) => {
                    console.log(`FFmpeg ASS subtitles command: ${cmdline}`);
                  })
                  .on("stderr", (stderrLine) => {
                    console.log(`FFmpeg ASS subtitles stderr: ${stderrLine}`);
                  })
                  .on("end", () => {
                    console.log("Successfully processed ASS subtitles");
                    currentVideoPath = assVideoPath;
                    resolve();
                  })
                  .on("error", (err) => {
                    console.error("FFmpeg ASS subtitles error:", err);
                    reject(err);
                  });

                command.run();
              });
            } catch (assError) {
              console.error(
                "Error with ASS subtitles, falling back to SRT:",
                assError
              );

              // If ASS format fails, fall back to simpler SRT format
              try {
                const srtSubtitlePath = path.join(tempDir, "subtitles.srt");
                await this.generateSRTSubtitles(subtitleClips, srtSubtitlePath);
                console.log(
                  `Created SRT subtitle file as fallback at ${srtSubtitlePath}`
                );

                const srtVideoPath = path.join(
                  tempDir,
                  "with_srt_subtitles.mp4"
                );

                // Properly escape the SRT path
                const escapedSrtPath = path
                  .resolve(srtSubtitlePath)
                  .replace(/\\/g, "/");

                // Ensure the subtitle path is properly escaped for ffmpeg
                const srtPathEscaped = escapedSrtPath.replace(
                  /([\\'])/g,
                  "\\$1"
                );
                console.log(`Using full SRT path (escaped): ${srtPathEscaped}`);

                // Create a simplified filter with proper escaping
                const subtitleFilter = `subtitles='${srtPathEscaped}':force_style='FontSize=52,FontName=Arial,PrimaryColour=&H00FFFFFF,OutlineColour=&H000000FF,BorderStyle=3,Outline=2,Shadow=0,Alignment=2,MarginV=150'`;
                console.log(`SRT subtitle filter: ${subtitleFilter}`);

                await new Promise<void>((resolve, reject) => {
                  const command = ffmpeg()
                    .input(currentVideoPath)
                    .outputOptions([
                      // Use subtitles filter with SRT format
                      "-vf",
                      subtitleFilter,
                      "-c:v",
                      "libx264",
                      "-preset",
                      "ultrafast",
                      "-crf",
                      "23",
                      "-c:a",
                      "copy",
                    ])
                    .output(srtVideoPath)
                    .on("start", (cmdline) => {
                      console.log(`FFmpeg SRT subtitles command: ${cmdline}`);
                    })
                    .on("stderr", (stderrLine) => {
                      console.log(`FFmpeg SRT subtitles stderr: ${stderrLine}`);
                    })
                    .on("end", () => {
                      console.log("Successfully processed SRT subtitles");
                      currentVideoPath = srtVideoPath;
                      resolve();
                    })
                    .on("error", (err) => {
                      console.error("FFmpeg SRT subtitles error:", err);
                      reject(err);
                    });

                  command.run();
                });
              } catch (srtError) {
                console.error(
                  "Error with SRT subtitles, falling back to drawtext method:",
                  srtError
                );

                // Final fallback to drawtext method
                try {
                  const drawTextVideoPath = path.join(
                    tempDir,
                    "with_drawtext_subtitles.mp4"
                  );

                  await this.createDrawTextSubtitles(
                    subtitleClips,
                    currentVideoPath,
                    drawTextVideoPath
                  );

                  currentVideoPath = drawTextVideoPath;
                  console.log("Successfully applied drawtext subtitles");
                } catch (drawTextError) {
                  console.error(
                    "Error with drawtext subtitles, proceeding without subtitles:",
                    drawTextError
                  );
                  // Continue without subtitles if all methods fail
                }
              }
            }
          } catch (error) {
            console.error("Error generating subtitles:", error);
            // Continue without subtitles if generation fails
          }
        }

        // Final copy to output path
        await fs.promises.copyFile(currentVideoPath, outputPath);
        console.log(`Copied final video to: ${outputPath}`);

        // Call the progress callback with 100% completion
        if (progressCallback) {
          progressCallback(100);
        }
      } finally {
        // Clean up temporary files
        try {
          if (fs.existsSync(tempDir)) {
            fs.rmSync(tempDir, { recursive: true, force: true });
          }
        } catch (e) {
          console.warn("Failed to clean up temp directory:", e);
        }
      }
    } catch (error) {
      console.error("Error rendering final video:", error);
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

  // Apply text effects to subtitle clips
  private applyTextEffects(textClips: TextClip[]): TextClip[] {
    // Create a distribution of effects for variety
    const usedEffects = new Map<string, number>();
    const subtitleClips = textClips.filter((clip) => !clip.isTitle);

    console.log(
      `Applying Pop-in Word by Word effect to all ${subtitleClips.length} subtitle clips`
    );

    // Find the Pop-in Word by Word Effect
    const popInEffect = this.textEffects.find(
      (effect) => effect.name === "Pop-in Word by Word"
    );

    if (!popInEffect) {
      console.warn("Pop-in Word by Word effect not found in effects list");
      return textClips;
    }

    // Apply Pop-in Word by Word effect to all non-title clips
    subtitleClips.forEach((clip) => {
      clip.effect = popInEffect;

      // Track usage of effects
      const count = usedEffects.get(popInEffect.name) || 0;
      usedEffects.set(popInEffect.name, count + 1);
    });

    // Log distribution of effects
    console.log("Text effects applied:");
    usedEffects.forEach((count, effectName) => {
      console.log(`  ${effectName}: ${count} clips`);
    });

    return textClips;
  }

  // Generate ASS subtitle format with advanced styling - simplified for better compatibility
  private async generateASSSubtitles(
    subtitleClips: TextClip[],
    outputPath: string,
    videoWidth?: number,
    videoHeight?: number
  ): Promise<void> {
    // Get width and height with safe defaults
    const width = videoWidth || this.width || this.WIDTH;
    const height = videoHeight || this.height || this.HEIGHT;

    // ASS header - using a very simplified header for maximum compatibility
    let assContent = `[Script Info]
ScriptType: v4.00+
PlayResX: ${width}
PlayResY: ${height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,52,&HFFFFFF&,&HFFFFFF&,&H000000&,&H000000&,1,0,0,0,100,100,0,0,1,2,0,2,20,20,150,0
`;

    // Events section - extremely simplified for maximum compatibility
    assContent += `
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`;

    // Add dialogue events for each subtitle clip - with minimal styling
    subtitleClips.forEach((clip, index) => {
      const startTime = this.formatASSTime(clip.start);
      const endTime = this.formatASSTime(clip.start + clip.duration);

      // Simple text without complex effects
      let text = clip.text.replace(/\n/g, "\\N").replace(/'/g, "\\'");

      // Apply animation effect if the clip has one
      if (clip.effect) {
        text = this.applyEffectToSubtitle(
          text,
          clip.effect,
          clip.start,
          clip.duration
        );

        // Apply color based on effect
        const effectColor = this.convertColorToASSFormat(
          clip.effect.fontColor || "white"
        );
        let styleOverrides = `\\c${effectColor}`;

        // Apply font name if specified
        if (clip.effect.fontName) {
          styleOverrides += `\\fn${clip.effect.fontName}`;
        }

        // Apply bold if specified
        if (clip.effect.isBold) {
          styleOverrides += "\\b1";
        }

        // Apply custom font size if specified
        if (clip.effect.fontSize) {
          styleOverrides += `\\fs${clip.effect.fontSize}`;
        }

        // Apply background if specified
        if (clip.effect.backgroundColor) {
          const bgColor = this.convertColorToASSFormat(
            clip.effect.backgroundColor.split("@")[0]
          );
          const bgAlpha = parseInt(
            (
              parseFloat(clip.effect.backgroundColor.split("@")[1] || "0.5") *
              255
            ).toString()
          );
          const bgAlphaHex = bgAlpha
            .toString(16)
            .padStart(2, "0")
            .toUpperCase();
          styleOverrides += `\\3c${bgColor}\\3a&H${bgAlphaHex}&`;
        }

        assContent += `Dialogue: 0,${startTime},${endTime},Default,,0,0,0,,{${styleOverrides}}${text}\n`;
      } else {
        // Add the dialogue line with the default style
        assContent += `Dialogue: 0,${startTime},${endTime},Default,,0,0,0,,${text}\n`;
      }
    });

    // Write to file
    await fs.promises.writeFile(outputPath, assContent);
    console.log(
      `ASS subtitle file written to ${outputPath} with content length: ${assContent.length}`
    );
    return;
  }

  // Generate SRT subtitle format as a fallback
  private async generateSRTSubtitles(
    subtitleClips: TextClip[],
    outputPath: string
  ): Promise<void> {
    let srtContent = "";

    subtitleClips.forEach((clip, index) => {
      const startTime = this.formatSrtTime(clip.start);
      const endTime = this.formatSrtTime(clip.start + clip.duration);

      // Simple clean text without effects
      const text = clip.text.replace(/\n/g, " ");

      // Add subtitle entry in SRT format
      srtContent += `${index + 1}\n${startTime} --> ${endTime}\n${text}\n\n`;
    });

    // Write to file
    await fs.promises.writeFile(outputPath, srtContent);
    console.log(
      `SRT subtitle file written to ${outputPath} with content length: ${srtContent.length}`
    );
    return;
  }

  // Format time for ASS format (h:mm:ss.cc)
  private formatASSTime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const cs = Math.floor((seconds % 1) * 100); // Centiseconds

    return `${h}:${m.toString().padStart(2, "0")}:${s
      .toString()
      .padStart(2, "0")}.${cs.toString().padStart(2, "0")}`;
  }

  // Helper method to convert regular color to ASS format
  private convertColorToASSFormat(color: string): string {
    // If it's already in ASS format, return as is
    if (color.startsWith("&H")) {
      return color;
    }

    // If it's a hex color like #RRGGBB
    if (color.startsWith("#")) {
      // ASS format is &HAABBGGRR (alpha, blue, green, red)
      const r = color.substr(1, 2);
      const g = color.substr(3, 2);
      const b = color.substr(5, 2);
      return `&H00${b}${g}${r}`;
    }

    // For named colors like "white", "yellow", just use a default format
    if (color === "white") return "&H00FFFFFF";
    if (color === "yellow") return "&H0000FFFF";
    if (color === "black") return "&H00000000";

    // Default
    return "&H0000FFFF"; // Yellow as default
  }

  // Apply the specific effect to ASS subtitle based on effect type
  private applyEffectToSubtitle(
    text: string,
    effect: TextEffect,
    start: number,
    duration: number
  ): string {
    // Base text with basic formatting
    let formattedText = text;

    console.log(
      `Applying effect "${effect.name}" to subtitle: "${text.substring(0, 30)}${
        text.length > 30 ? "..." : ""
      }"`
    );

    // Apply effect-specific styling
    switch (effect.name) {
      case "Pop-in Word by Word":
        // Split into words and add scale animation for each word
        const words = text.split(" ");
        formattedText = words
          .map((word, i) => {
            const delay = i * 0.2;
            const wordStart = start + delay;
            const wordEnd = start + duration;
            return `{\\fad(200,200)\\t(${wordStart * 100},${
              (wordStart + 0.2) * 100
            },\\fscx120\\fscy120)\\t(${(wordStart + 0.2) * 100},${
              (wordStart + 0.4) * 100
            },\\fscx100\\fscy100)}${word}`;
          })
          .join(" ");
        break;

      case "Typewriter Effect":
        // Apply typewriter effect with a more visible letter-by-letter appearance
        // Simulate typing by using \k tag which controls timing for karaoke effects
        const letters = text.split("");
        const letterDelay = 10; // 10 centiseconds per letter

        // Create a string with timing for each letter
        let typedText = "";
        letters.forEach((letter, index) => {
          typedText += `{\\k${letterDelay}}${letter}`;
        });

        // Add a blinking cursor effect at the end
        formattedText = `{\\fad(300,300)\\t(0,${
          text.length * letterDelay * 10
        },\\alpha&H00&)}${typedText}{\\alpha&H00&\\t(0,500,\\alpha&HFF&)\\t(500,1000,\\alpha&H00&)\\t(1000,1500,\\alpha&HFF&)\\t(1500,2000,\\alpha&H00&)}|`;
        break;

      case "Bouncy Word Effect":
        // Apply bouncy effect
        formattedText = `{\\t(0,200,\\frz-5)\\t(200,400,\\frz5)\\t(400,600,\\frz0)}${text}`;
        break;

      case "Wave Motion":
        // Apply wave motion to text
        formattedText = `{\\t(0,1000,\\fry10\\frx5)\\t(1000,2000,\\fry-10\\frx-5)\\t(2000,3000,\\fry0\\frx0)}${text}`;
        break;

      case "Glitchy Text":
        // Apply glitch effect
        formattedText = `{\\fad(300,300)\\t(0,100,\\fscx110\\frz3)\\t(100,200,\\fscx90\\frz-3)\\t(200,300,\\fscx100\\frz0)}${text}`;
        break;

      case "Sliding Subtitles":
        // Apply sliding effect - fixed to use proper coordinates
        formattedText = `{\\move(-100,10,10,10,0,500)}${text}`;
        break;

      case "Shake Effect":
        // Apply shake effect
        formattedText = `{\\t(0,100,\\frz2\\fscx102)\\t(100,200,\\frz-2\\fscx98)\\t(200,300,\\frz1\\fscx102)\\t(300,400,\\frz-1\\fscx100)}${text}`;
        break;

      case "Expanding Words":
        // Apply expanding effect
        formattedText = `{\\t(0,500,\\fscx50\\fscy50)\\t(500,1000,\\fscx110\\fscy110)\\t(1000,1500,\\fscx100\\fscy100)}${text}`;
        break;

      case "3D Rotation Effect":
        // Apply 3D rotation effect
        formattedText = `{\\t(0,500,\\frx45)\\t(500,1000,\\frx0)}${text}`;
        break;

      case "Handwritten Scribble Text":
        // Apply handwritten effect
        formattedText = `{\\fad(1000,300)}${text}`;
        break;

      default:
        // No special effect
        formattedText = text;
    }

    console.log(
      `Effect applied, result: "${formattedText.substring(0, 50)}${
        formattedText.length > 50 ? "..." : ""
      }"`
    );
    return formattedText;
  }

  // Fallback method using drawtext for subtitles
  private createDrawTextSubtitles(
    subtitleClips: TextClip[],
    videoPath: string,
    outputPath: string
  ): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      try {
        console.log("Attempting drawtext method for subtitles");

        // Create filter complex commands for each subtitle
        const filterCommands: string[] = [];

        // Font file path - use system font if available
        let fontFile = "";
        const systemFontPath =
          process.platform === "darwin"
            ? "/System/Library/Fonts/Helvetica.ttc"
            : process.platform === "win32"
            ? "C:\\Windows\\Fonts\\arial.ttf"
            : "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf";

        if (fs.existsSync(systemFontPath)) {
          fontFile = `:fontfile='${systemFontPath
            .replace(/\\/g, "\\\\")
            .replace(/'/g, "\\'")}'`;
          console.log(`Using system font: ${systemFontPath}`);
        } else {
          console.log("System font not found, using default font");
        }

        subtitleClips.forEach((clip) => {
          // Format timestamps in seconds for enable/disable expressions
          const startTimeSeconds = clip.start;
          const endTimeSeconds = clip.start + clip.duration;

          // Escape text for FFmpeg
          const text = clip.text
            .replace(/\\/g, "\\\\")
            .replace(/'/g, "\\\\'")
            .replace(/:/g, "\\:");

          // Create drawtext filter with enable/disable timing
          const drawTextCmd = `drawtext=text='${text}'${fontFile}:fontsize=52:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=h-th-200:enable='between(t,${startTimeSeconds},${endTimeSeconds})'`;

          filterCommands.push(drawTextCmd);
        });

        // Join all filters
        const filterComplex = filterCommands.join(",");
        console.log(
          `Using drawtext method with ${filterCommands.length} subtitle clips`
        );

        // Apply the filters
        const command = ffmpeg()
          .input(videoPath)
          .outputOptions([
            "-vf",
            filterComplex,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-c:a",
            "copy",
          ])
          .output(outputPath)
          .on("start", (cmdline) => {
            console.log(`FFmpeg drawtext subtitles command: ${cmdline}`);
          })
          .on("stderr", (stderrLine) => {
            console.log(`FFmpeg drawtext stderr: ${stderrLine}`);
          })
          .on("end", () => {
            console.log("Successfully processed drawtext subtitles");
            resolve();
          })
          .on("error", (err) => {
            console.error("FFmpeg drawtext error:", err);
            reject(err);
          });

        command.run();
      } catch (error) {
        console.error("Error in drawtext method:", error);
        reject(error);
      }
    });
  }

  // Helper method to add subtitles to a video
  private addSubtitlesToVideo(
    inputVideoPath: string,
    outputVideoPath: string,
    subtitleFilter: string
  ): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      try {
        console.log(`Adding subtitles to video with filter: ${subtitleFilter}`);

        const command = ffmpeg()
          .input(inputVideoPath)
          .outputOptions([
            "-vf",
            subtitleFilter,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-c:a",
            "copy",
          ])
          .output(outputVideoPath)
          .on("start", (cmdline) => {
            console.log(`FFmpeg subtitles command: ${cmdline}`);
          })
          .on("stderr", (stderrLine) => {
            console.log(`FFmpeg subtitles stderr: ${stderrLine}`);
          })
          .on("end", () => {
            console.log(
              `Successfully added subtitles to video: ${outputVideoPath}`
            );
            resolve();
          })
          .on("error", (err) => {
            console.error("FFmpeg subtitles error:", err);
            reject(err);
          });

        command.run();
      } catch (error) {
        console.error("Error in addSubtitlesToVideo:", error);
        reject(error);
      }
    });
  }

  // Helper method to merge voiceover with background video
  private mergeVoiceoverWithVideo(
    voiceoverPath: string,
    videoPath: string,
    outputPath: string
  ): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      try {
        console.log(
          `Merging voiceover ${voiceoverPath} with video ${videoPath}`
        );

        const command = ffmpeg()
          .input(videoPath)
          .input(voiceoverPath)
          .outputOptions([
            "-map",
            "0:v", // Use video from first input
            "-map",
            "1:a", // Use audio from second input
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
          ])
          .output(outputPath)
          .on("start", (cmdline) => {
            console.log(`FFmpeg merge command: ${cmdline}`);
          })
          .on("end", () => {
            console.log(
              `Successfully merged voiceover with video: ${outputPath}`
            );
            resolve();
          })
          .on("error", (err) => {
            console.error("FFmpeg merge error:", err);
            reject(err);
          });

        command.run();
      } catch (error) {
        console.error("Error in mergeVoiceoverWithVideo:", error);
        reject(error);
      }
    });
  }

  private async generateAudioTranscript(
    audioPath: string,
    language: string = "en"
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
        console.warn(
          "Whisper transcription script not found, returning empty transcript"
        );
        return {
          text: "",
          segments: [],
        };
      }

      // Check if virtual environment exists
      if (!fs.existsSync(venvPythonPath)) {
        console.warn(
          "Python virtual environment not found, returning empty transcript"
        );
        return {
          text: "",
          segments: [],
        };
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

  private generateThumbnail(
    videoPath: string,
    thumbnailPath: string
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      console.log(`Generating thumbnail from video: ${videoPath}`);
      ffmpeg(videoPath)
        .screenshots({
          timestamps: ["00:00:01"],
          filename: path.basename(thumbnailPath),
          folder: path.dirname(thumbnailPath),
          size: `${this.width}x${this.height}`,
        })
        .on("end", () => {
          console.log(`Generated thumbnail at: ${thumbnailPath}`);
          resolve();
        })
        .on("error", (err: Error) => {
          console.error("Error generating thumbnail:", err);
          reject(err);
        });
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

      if (!this.openaiClient) {
        throw new Error("Failed to initialize OpenAI client");
      }

      const response = await this.openaiClient.chat.completions.create({
        model: "gpt-4o-mini",
        messages: [
          {
            role: "assistant",
            content: this.getPromptGenerationSystemMessage(),
          },
          {
            role: "user",
            content: `Generate ${
              this.currentFormat === "shorts" ? "9" : "18"
            } image prompts for this script: ${script}`,
          },
        ],
        temperature: 0.7,
      });

      console.log("OpenAI response:", response.choices[0].message);

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
      // Return some default prompts as fallback
      return [
        "Cinematic landscape view, golden hour lighting, soft focus",
        "Close-up portrait, shallow depth of field, natural lighting",
        "Urban cityscape, neon lights, night photography",
        "Nature scene, vibrant colors, ultra wide angle lens",
        "Minimalist composition, high contrast, black and white photography",
        "Aerial view, dramatic perspective, wide landscape shot",
        "Motion blur photography, long exposure, dynamic movement",
        "Abstract geometric patterns, macro photography, vivid colors",
        "Silhouette against sunset, dramatic sky, telephoto lens",
      ];
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
}

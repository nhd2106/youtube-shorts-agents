"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.VideoGenerator = void 0;
const path_1 = __importDefault(require("path"));
const fs_1 = __importDefault(require("fs"));
const fluent_ffmpeg_1 = __importDefault(require("fluent-ffmpeg"));
const openai_1 = require("openai");
const child_process_1 = require("child_process");
const os_1 = __importDefault(require("os"));
class VideoGenerator {
    constructor() {
        this.WIDTH = 1080;
        this.HEIGHT = 1920;
        this.DURATION = 60;
        this.textEffects = [
            {
                name: "Pop-in Word by Word",
                style: "bold",
                animationParams: { scale: "1.2", fade: "0.3" },
                fontColor: "white",
                stroke: true,
                strokeColor: "black",
            },
            {
                name: "Typewriter Effect",
                style: "monospace",
                animationParams: { typingSpeed: "0.05", cursor: true },
                fontColor: "white",
                backgroundColor: "black@0.6",
                fontName: "Courier New",
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
        const baseDir = process.cwd();
        this.defaultTempDir = path_1.default.join(baseDir, "contents", "temp");
        fs_1.default.mkdirSync(this.defaultTempDir, { recursive: true });
    }
    initOpenAIClient(apiKey) {
        if (!apiKey) {
            throw new Error("OpenAI API key is required for prompt generation");
        }
        this.openaiClient = new openai_1.OpenAI({ apiKey });
    }
    setFormat(formatType) {
        if (!this.videoFormats[formatType]) {
            throw new Error(`Invalid format type. Choose from: ${Object.keys(this.videoFormats).join(", ")}`);
        }
        if (this.currentFormat !== formatType) {
            this.currentFormat = formatType;
            this.width = this.videoFormats[formatType].width;
            this.height = this.videoFormats[formatType].height;
        }
    }
    splitIntoPhrases(text) {
        const pattern = /([.!?,;:])/;
        const sentences = text.split(pattern).filter(Boolean);
        const phrases = [];
        let currentPhrase = "";
        for (const item of sentences) {
            if (!item.trim())
                continue;
            if (pattern.test(item)) {
                currentPhrase += item;
                phrases.push(currentPhrase.trim());
                currentPhrase = "";
            }
            else {
                if (currentPhrase) {
                    phrases.push(currentPhrase.trim());
                }
                currentPhrase = item;
            }
        }
        if (currentPhrase) {
            phrases.push(currentPhrase.trim());
        }
        return phrases
            .filter((phrase) => phrase.trim())
            .map((phrase) => phrase.replace(/\s+/g, " ").trim());
    }
    async generateVideo(audioPath, content, requestId, backgroundImages, progressCallback) {
        try {
            this.duration = await this.getAudioDuration(audioPath);
            if (!this.duration) {
                throw new Error("Could not determine audio duration");
            }
            if (!backgroundImages ||
                !Array.isArray(backgroundImages) ||
                backgroundImages.length === 0) {
                throw new Error("No background images provided");
            }
            const requestDir = path_1.default.join(process.cwd(), "contents", requestId);
            const videoDir = path_1.default.join(requestDir, "video");
            const scriptDir = path_1.default.join(requestDir, "script");
            await fs_1.default.promises.mkdir(requestDir, { recursive: true, mode: 0o755 });
            await fs_1.default.promises.mkdir(videoDir, { recursive: true, mode: 0o755 });
            await fs_1.default.promises.mkdir(scriptDir, { recursive: true, mode: 0o755 });
            const videoPath = path_1.default.join(videoDir, `${requestId}.mp4`);
            const thumbnailPath = path_1.default.join(videoDir, `${requestId}_thumbnail.jpg`);
            const scriptPath = path_1.default.join(scriptDir, `${requestId}.txt`);
            const segments = await this.createVideoSegments(backgroundImages);
            let transcriptText = content.script;
            let transcriptSegments = [];
            try {
                const transcriptResult = await this.generateAudioTranscript(audioPath);
                if (transcriptResult && transcriptResult.segments) {
                    transcriptSegments = transcriptResult.segments.map((segment) => ({
                        text: segment.text.trim(),
                        start: segment.start,
                        end: segment.end,
                        duration: segment.end - segment.start,
                    }));
                    transcriptText = transcriptResult.text;
                }
            }
            catch (error) {
                console.warn("Using original script as fallback:", error.message);
                transcriptSegments = this.splitIntoPhrases(transcriptText).map((phrase, index, array) => {
                    const segmentDuration = this.duration / array.length;
                    return {
                        text: phrase,
                        start: index * segmentDuration,
                        end: (index + 1) * segmentDuration,
                        duration: segmentDuration,
                    };
                });
            }
            await fs_1.default.promises.writeFile(scriptPath, transcriptText);
            const textClips = [];
            const titleDuration = this.duration;
            textClips.push({
                text: content.title,
                start: 0,
                duration: titleDuration,
                isTitle: true,
            });
            textClips.push(...transcriptSegments.map((segment) => ({
                text: segment.text,
                start: segment.start,
                duration: segment.duration,
                isTitle: false,
            })));
            const textClipsWithEffects = this.applyTextEffects(textClips);
            await this.renderFinalVideo(segments, textClipsWithEffects, audioPath, videoPath, progressCallback);
            await this.generateThumbnail(videoPath, thumbnailPath);
            for (const segment of segments) {
                try {
                    if (fs_1.default.existsSync(segment)) {
                        await fs_1.default.promises.unlink(segment);
                    }
                }
                catch (error) {
                    console.warn(`Failed to clean up segment: ${segment}`, error);
                }
            }
            return {
                videoPath,
                thumbnailPath,
                scriptPath,
            };
        }
        catch (error) {
            console.error("Error generating video:", error);
            throw error;
        }
    }
    getAudioDuration(audioPath) {
        return new Promise((resolve, reject) => {
            fluent_ffmpeg_1.default.ffprobe(audioPath, (err, metadata) => {
                if (err)
                    reject(err);
                else
                    resolve(metadata.format.duration || 0);
            });
        });
    }
    async createVideoSegments(backgroundImages) {
        if (!this.width || !this.height || !this.duration || !this.currentFormat) {
            throw new Error("Video dimensions, duration, and format must be set first");
        }
        const validImages = backgroundImages.filter((img) => fs_1.default.existsSync(img));
        if (validImages.length === 0) {
            throw new Error("No valid background images found");
        }
        const tempDir = path_1.default.join(process.cwd(), "contents", "temp", `segments_${Date.now()}`);
        try {
            fs_1.default.mkdirSync(tempDir, { recursive: true, mode: 0o755 });
        }
        catch (error) {
            console.error("Error creating temp directory:", error);
            throw new Error(`Failed to create temp directory: ${error.message}`);
        }
        const segmentDuration = this.duration / validImages.length;
        const segments = [];
        try {
            for (let i = 0; i < validImages.length; i++) {
                const imagePath = validImages[i];
                const outputPath = path_1.default.join(tempDir, `segment_${i}.mp4`);
                const zoomStart = 1.0;
                const zoomEnd = 1.05;
                const panX = Math.random() * 60 - 30;
                const panY = Math.random() * 60 - 30;
                const filterComplex = [
                    `scale=${this.width}:${this.height}:force_original_aspect_ratio=increase`,
                    `crop=${this.width}:${this.height}`,
                    `zoompan=z='if(lte(zoom,${zoomStart}),${zoomStart},min(zoom+0.0005,${zoomEnd}))':` +
                        `x='iw/2-(iw/zoom/2)+(${panX}*sin(on/${Math.ceil(segmentDuration * 30)}/PI))':` +
                        `y='ih/2-(ih/zoom/2)+(${panY}*sin(on/${Math.ceil(segmentDuration * 30)}/PI))':` +
                        `d=${Math.ceil(segmentDuration * 30)}:s=${this.width}x${this.height}:fps=30`,
                    `fade=t=in:st=0:d=0.5,fade=t=out:st=${segmentDuration - 0.5}:d=0.5`,
                ].join(",");
                await new Promise((resolve, reject) => {
                    const command = (0, fluent_ffmpeg_1.default)()
                        .input(imagePath)
                        .inputOptions(["-loop 1"])
                        .outputOptions([
                        `-t ${segmentDuration}`,
                        "-pix_fmt yuv420p",
                        "-r 30",
                        "-c:v libx264",
                        "-preset veryfast",
                        "-profile:v high",
                        "-level 4.2",
                        "-crf 23",
                        "-maxrate 5M",
                        "-bufsize 10M",
                        "-movflags +faststart",
                        "-y",
                    ])
                        .complexFilter(filterComplex)
                        .output(outputPath);
                    command.on("start", () => {
                    });
                    command.on("stderr", () => {
                    });
                    command.on("end", () => {
                        if (fs_1.default.existsSync(outputPath)) {
                            segments.push(outputPath);
                            resolve();
                        }
                        else {
                            reject(new Error(`Failed to create segment ${i}: Output file not found`));
                        }
                    });
                    command.on("error", (err) => {
                        console.error(`Error creating segment ${i}:`, err);
                        reject(err);
                    });
                    command.run();
                });
                if (!fs_1.default.existsSync(segments[segments.length - 1])) {
                    throw new Error(`Segment ${i} was not created successfully`);
                }
            }
            return segments;
        }
        catch (error) {
            segments.forEach((segment) => {
                try {
                    if (fs_1.default.existsSync(segment))
                        fs_1.default.unlinkSync(segment);
                }
                catch (e) {
                    console.warn(`Failed to clean up segment: ${segment}`, e);
                }
            });
            try {
                if (fs_1.default.existsSync(tempDir)) {
                    fs_1.default.rmSync(tempDir, { recursive: true, force: true });
                }
            }
            catch (e) {
                console.warn("Failed to clean up temp directory:", e);
            }
            throw error;
        }
    }
    async renderFinalVideo(segments, textClips, audioPath, outputPath, progressCallback) {
        try {
            outputPath = path_1.default.resolve(outputPath);
            audioPath = path_1.default.resolve(audioPath);
            segments = segments.map((s) => path_1.default.resolve(s));
            console.log(`Processing video with ${segments.length} segments and ${textClips.length} text clips`);
            console.log(`Output path: ${outputPath}`);
            console.log(`Audio path: ${audioPath}`);
            const outputDir = path_1.default.dirname(outputPath);
            await fs_1.default.promises.mkdir(outputDir, { recursive: true, mode: 0o755 });
            const tempDir = path_1.default.join(os_1.default.tmpdir(), `ffmpeg_${Date.now()}`);
            await fs_1.default.promises.mkdir(tempDir, { recursive: true, mode: 0o755 });
            console.log(`Created temp directory: ${tempDir}`);
            try {
                const concatFilePath = path_1.default.join(tempDir, "concat.txt");
                const concatContent = segments
                    .map((segment) => `file '${segment.replace(/'/g, "'\\''")}'`)
                    .join("\n");
                await fs_1.default.promises.writeFile(concatFilePath, concatContent);
                console.log(`Created concat file at ${concatFilePath}`);
                const baseVideoPath = path_1.default.join(tempDir, "base.mp4");
                await new Promise((resolve, reject) => {
                    const command = (0, fluent_ffmpeg_1.default)()
                        .input(concatFilePath)
                        .inputOptions(["-f", "concat", "-safe", "0"])
                        .input(audioPath)
                        .outputOptions([
                        "-map",
                        "0:v",
                        "-map",
                        "1:a",
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
                    })
                        .on("stderr", () => {
                    })
                        .on("end", () => resolve())
                        .on("error", (err) => {
                        console.error("FFmpeg base error:", err);
                        reject(err);
                    });
                    command.run();
                });
                let currentVideoPath = baseVideoPath;
                const titleClip = textClips.find((clip) => clip.isTitle);
                if (titleClip) {
                    const withTitlePath = path_1.default.join(tempDir, "with_title.mp4");
                    const effectiveWidth = this.WIDTH * 0.8;
                    const charsPerLine = Math.floor(effectiveWidth / 25);
                    console.log(`Using ${charsPerLine} characters per line for title (80% of ${this.WIDTH}px width)`);
                    const wrappedTitleText = this.wrapText(titleClip.text, charsPerLine);
                    const lines = wrappedTitleText.split("\n");
                    let drawTextFilters = "";
                    const lineHeight = 60;
                    lines.forEach((line, index) => {
                        const escapedLine = line
                            .replace(/\\/g, "\\\\")
                            .replace(/:/g, "\\:")
                            .replace(/'/g, "\\\\'");
                        const lineY = Math.floor(this.HEIGHT * 0.25) + index * lineHeight;
                        if (index > 0)
                            drawTextFilters += ",";
                        drawTextFilters += `drawtext=text='${escapedLine}':fontfile=${path_1.default.resolve("assets/fonts/Arial.ttf")}:fontsize=50:fontcolor=yellow:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=${lineY}`;
                    });
                    console.log(`Wrapped title into ${lines.length} lines with ${charsPerLine} chars per line`);
                    console.log(`Draw text filters: ${drawTextFilters}`);
                    await new Promise((resolve, reject) => {
                        const command = (0, fluent_ffmpeg_1.default)()
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
                const subtitleClips = textClips.filter((clip) => !clip.isTitle);
                if (subtitleClips.length > 0) {
                    try {
                        const assSubtitlePath = path_1.default.join(tempDir, "subtitles.ass");
                        const assContent = this.generateASSSubtitles(subtitleClips);
                        await fs_1.default.promises.writeFile(assSubtitlePath, assContent);
                        console.log(`Created ASS subtitle file at ${assSubtitlePath} with content length: ${assContent.length}`);
                        console.log("ASS file first 10 lines:", assContent.split("\n").slice(0, 10).join("\n"));
                        const assVideoPath = path_1.default.join(tempDir, "with_ass_subtitles.mp4");
                        const escapedSubtitlePath = path_1.default
                            .resolve(assSubtitlePath)
                            .replace(/\\/g, "/");
                        console.log(`Using subtitle path: ${escapedSubtitlePath}`);
                        try {
                            await new Promise((resolve, reject) => {
                                const command = (0, fluent_ffmpeg_1.default)()
                                    .input(currentVideoPath)
                                    .outputOptions([
                                    "-vf",
                                    `subtitles=${escapedSubtitlePath}`,
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
                        }
                        catch (assError) {
                            console.error("Error with ASS subtitles, falling back to SRT:", assError);
                            const srtSubtitlePath = path_1.default.join(tempDir, "subtitles.srt");
                            const srtContent = this.generateSRTSubtitles(subtitleClips);
                            await fs_1.default.promises.writeFile(srtSubtitlePath, srtContent);
                            console.log(`Created SRT subtitle file as fallback at ${srtSubtitlePath}`);
                            const srtVideoPath = path_1.default.join(tempDir, "with_srt_subtitles.mp4");
                            const escapedSrtPath = path_1.default
                                .resolve(srtSubtitlePath)
                                .replace(/\\/g, "/");
                            await new Promise((resolve, reject) => {
                                const command = (0, fluent_ffmpeg_1.default)()
                                    .input(currentVideoPath)
                                    .outputOptions([
                                    "-vf",
                                    `subtitles=${escapedSrtPath}:force_style='FontSize=24,FontName=Arial,PrimaryColour=&H00FFFFFF,OutlineColour=&H000000FF,BorderStyle=3,Outline=2,Shadow=0,Alignment=2'`,
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
                        }
                    }
                    catch (subtitleError) {
                        console.error("Error processing subtitles:", subtitleError);
                        console.warn("Continuing without subtitles due to errors");
                    }
                }
                await fs_1.default.promises.copyFile(currentVideoPath, outputPath);
                console.log(`Final video saved to ${outputPath}`);
                if (progressCallback) {
                    progressCallback(100);
                }
            }
            finally {
                try {
                    await fs_1.default.promises.rm(tempDir, { recursive: true, force: true });
                    console.log(`Cleaned up temp directory: ${tempDir}`);
                }
                catch (error) {
                    console.error(`Error cleaning up temp directory: ${error}`);
                }
            }
        }
        catch (error) {
            console.error("Error in renderFinalVideo:", error);
            throw error;
        }
    }
    wrapText(text, maxCharsPerLine) {
        const words = text.split(" ");
        const lines = [];
        let currentLine = "";
        for (let i = 0; i < words.length; i++) {
            const word = words[i];
            if (word.length > maxCharsPerLine) {
                if (currentLine.length > 0) {
                    lines.push(currentLine);
                    currentLine = "";
                }
                let remainingWord = word;
                while (remainingWord.length > 0) {
                    const chunkSize = Math.min(maxCharsPerLine - 1, remainingWord.length);
                    const chunk = remainingWord.substring(0, chunkSize) +
                        (remainingWord.length > chunkSize ? "-" : "");
                    lines.push(chunk);
                    remainingWord = remainingWord.substring(chunkSize);
                }
                continue;
            }
            if (currentLine.length + word.length + 1 > maxCharsPerLine &&
                currentLine.length > 0) {
                lines.push(currentLine);
                currentLine = word;
            }
            else {
                currentLine =
                    currentLine.length === 0 ? word : `${currentLine} ${word}`;
            }
        }
        if (currentLine.length > 0) {
            lines.push(currentLine);
        }
        return lines.join("\n");
    }
    generateThumbnail(videoPath, thumbnailPath) {
        return new Promise((resolve, reject) => {
            (0, fluent_ffmpeg_1.default)(videoPath)
                .screenshots({
                timestamps: ["00:00:01"],
                filename: path_1.default.basename(thumbnailPath),
                folder: path_1.default.dirname(thumbnailPath),
                size: `${this.width}x${this.height}`,
            })
                .on("end", () => resolve())
                .on("error", (err) => reject(err));
        });
    }
    async generatePromptsWithOpenAI(script, apiKeys) {
        try {
            if (!apiKeys.openai) {
                throw new Error("OpenAI API key is required for prompt generation");
            }
            if (!this.currentFormat) {
                throw new Error("Video format must be set before generating prompts");
            }
            this.initOpenAIClient(apiKeys.openai);
            const response = await this.openaiClient.chat.completions.create({
                model: "gpt-4o-mini",
                messages: [
                    {
                        role: "assistant",
                        content: this.getPromptGenerationSystemMessage(),
                    },
                    {
                        role: "user",
                        content: `Generate ${this.currentFormat ?? "shorts" === "shorts" ? "9" : "18"} image prompts for this script: ${script}`,
                    },
                ],
                temperature: 0.7,
            });
            console.log(response.choices[0].message);
            const content = response.choices[0].message.content;
            if (!content) {
                throw new Error("No prompts generated");
            }
            const prompts = content
                .split("\n")
                .map((line) => line.trim())
                .map((line) => {
                const withoutNumber = line.replace(/^\d+\.\s*/, "");
                const withoutFormatting = withoutNumber.replace(/\*\*/g, "");
                return withoutFormatting.trim();
            })
                .filter((line) => line.length > 0 && !line.startsWith("#") && !line.match(/^\s*$/));
            console.log(`Generated ${prompts.length} prompts for ${this.currentFormat} format`);
            return prompts;
        }
        catch (error) {
            console.error("Error generating prompts:", error);
            console.warn("Using default prompts as fallback");
        }
    }
    getPromptGenerationSystemMessage() {
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
    async generateAudioTranscript(audioPath, language = "vi") {
        try {
            if (!fs_1.default.existsSync(audioPath)) {
                throw new Error(`Audio file not found at path: ${audioPath}`);
            }
            const scriptPath = path_1.default.join(__dirname, "whisper_transcribe.py");
            const venvPath = path_1.default.join(__dirname, "venv");
            const venvPythonPath = path_1.default.join(venvPath, "bin", "python3");
            const venvSitePackages = path_1.default.join(venvPath, "lib", "python3.11", "site-packages");
            if (!fs_1.default.existsSync(scriptPath)) {
                throw new Error("Whisper transcription script not found");
            }
            if (!fs_1.default.existsSync(venvPythonPath)) {
                throw new Error("Python virtual environment not found. Please run setup_whisper.sh first");
            }
            console.log(`Transcribing audio file: ${audioPath}`);
            return new Promise((resolve) => {
                const env = {
                    ...process.env,
                    PYTHONPATH: venvSitePackages,
                    PATH: `${path_1.default.join(venvPath, "bin")}:${process.env.PATH}`,
                };
                const pythonProcess = (0, child_process_1.spawn)(venvPythonPath, [scriptPath, audioPath, language], {
                    env,
                });
                let outputData = "";
                let errorData = "";
                pythonProcess.stdout.on("data", (data) => {
                    outputData += data.toString();
                });
                pythonProcess.stderr.on("data", (data) => {
                    errorData += data.toString();
                    if (!data.toString().includes("Using device:")) {
                        console.warn(`Python stderr: ${data}`);
                    }
                });
                pythonProcess.on("close", (code) => {
                    if (code !== 0) {
                        console.error(`Python process exited with code ${code}`);
                        console.error("Error output:", errorData);
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
                    }
                    catch (e) {
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
        }
        catch (error) {
            console.error("Error generating audio transcript:", error);
            return {
                text: "",
                segments: [],
            };
        }
    }
    async generateOptimizedTranscript(audioPath, originalScript, language = "en") {
        try {
            const transcriptResult = await this.generateAudioTranscript(audioPath, language);
            const audioTranscript = transcriptResult.text;
            if (originalScript) {
                return originalScript;
            }
            return audioTranscript;
        }
        catch (error) {
            console.error("Error generating optimized transcript:", error);
            if (originalScript) {
                console.warn("Falling back to original script");
                return originalScript;
            }
            throw error;
        }
    }
    async getPreciseWordTimings(audioPath, script) {
        try {
            const transcriptResult = await this.generateAudioTranscript(audioPath);
            if (transcriptResult.segments && transcriptResult.segments.length > 0) {
                const wordTimings = transcriptResult.segments.flatMap((segment) => segment.words
                    ? segment.words.map((word) => ({
                        word: word.text,
                        start: word.start,
                        end: word.end,
                    }))
                    : []);
                return wordTimings;
            }
            else {
                return this.getSimpleWordTimings(audioPath, script);
            }
        }
        catch (error) {
            console.error("Error getting word timings:", error);
            return this.getSimpleWordTimings(audioPath, script);
        }
    }
    async getSimpleWordTimings(audioPath, script) {
        const audioAnalysis = await this.analyzeAudio(audioPath);
        const words = script.split(/\s+/);
        const audioDuration = audioAnalysis.duration;
        const avgWordDuration = audioDuration / words.length;
        return words.map((word, index) => ({
            word,
            start: index * avgWordDuration,
            end: (index + 1) * avgWordDuration,
        }));
    }
    async analyzeAudio(audioPath) {
        const ffprobe = require("ffprobe");
        const ffprobeStatic = require("ffprobe-static");
        const { streams } = await ffprobe(audioPath, { path: ffprobeStatic.path });
        const audioStream = streams.find((s) => s.codec_type === "audio");
        return {
            duration: audioStream ? parseFloat(audioStream.duration) : 0,
        };
    }
    formatSrtTime(seconds) {
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
    getRandomTextEffect() {
        const randomIndex = Math.floor(Math.random() * this.textEffects.length);
        return this.textEffects[randomIndex];
    }
    applyTextEffects(textClips) {
        const usedEffects = new Map();
        return textClips.map((clip) => {
            if (!clip.isTitle) {
                const effect = this.getRandomTextEffect();
                clip.effect = effect;
                const count = usedEffects.get(effect.name) || 0;
                usedEffects.set(effect.name, count + 1);
            }
            return clip;
        });
        console.log("Text effects distribution:");
        usedEffects.forEach((count, effectName) => {
            console.log(`${effectName}: ${count} clips`);
        });
        return textClips;
    }
    generateASSSubtitles(subtitleClips) {
        const videoWidth = this.width || this.WIDTH;
        const videoHeight = this.height || this.HEIGHT;
        let assContent = `[Script Info]
ScriptType: v4.00+
PlayResX: ${videoWidth}
PlayResY: ${videoHeight}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
`;
        assContent += `Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n`;
        this.textEffects.forEach((effect) => {
            const fontName = effect.fontName || "Arial";
            const primaryColor = this.convertColorToASSFormat(effect.fontColor);
            assContent += `Style: ${effect.name.replace(/\s+/g, "")},${fontName},24,${primaryColor},&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n`;
        });
        assContent += `
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`;
        subtitleClips.forEach((clip) => {
            const effect = clip.effect || this.getRandomTextEffect();
            const startTime = this.formatASSTime(clip.start);
            const endTime = this.formatASSTime(clip.start + clip.duration);
            const styleName = effect.name.replace(/\s+/g, "");
            const text = `{\\fad(200,200)}${clip.text}`;
            assContent += `Dialogue: 0,${startTime},${endTime},${styleName},,0,0,0,,${text}\n`;
        });
        return assContent;
    }
    generateSRTSubtitles(subtitleClips) {
        let srtContent = "";
        subtitleClips.forEach((clip, index) => {
            const startTime = this.formatSrtTime(clip.start);
            const endTime = this.formatSrtTime(clip.start + clip.duration);
            const text = clip.text.replace(/\n/g, " ");
            srtContent += `${index + 1}\n${startTime} --> ${endTime}\n${text}\n\n`;
        });
        return srtContent;
    }
    formatASSTime(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        const cs = Math.floor((seconds % 1) * 100);
        return `${h}:${m.toString().padStart(2, "0")}:${s
            .toString()
            .padStart(2, "0")}.${cs.toString().padStart(2, "0")}`;
    }
    convertColorToASSFormat(color) {
        if (color.startsWith("&H")) {
            return color;
        }
        if (color.startsWith("#")) {
            const r = color.substr(1, 2);
            const g = color.substr(3, 2);
            const b = color.substr(5, 2);
            return `&H00${b}${g}${r}`;
        }
        if (color === "white")
            return "&H00FFFFFF";
        if (color === "yellow")
            return "&H0000FFFF";
        if (color === "black")
            return "&H00000000";
        return "&H0000FFFF";
    }
}
exports.VideoGenerator = VideoGenerator;
//# sourceMappingURL=VideoGenerator.js.map
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const path_1 = __importDefault(require("path"));
const fs_1 = __importDefault(require("fs"));
const dotenv_1 = require("dotenv");
const RequestTracker_1 = require("./services/RequestTracker");
const ContentGenerator_1 = require("./services/ContentGenerator");
const AudioGenerator_1 = require("./services/AudioGenerator");
const VideoGenerator_1 = require("./services/VideoGenerator");
const ImageHandler_1 = require("./services/ImageHandler");
const types_1 = require("./types");
(0, dotenv_1.config)();
const args = process.argv.slice(2);
const portArg = args.find((arg) => arg.startsWith("--port="));
const PORT = portArg
    ? parseInt(portArg.split("=")[1], 10)
    : process.env.PORT
        ? parseInt(process.env.PORT, 10)
        : 3000;
console.log(`Starting YouTube Shorts Agent server on port ${PORT}`);
console.log(`Process ID: ${process.pid}`);
console.log(`Working directory: ${process.cwd()}`);
const app = (0, express_1.default)();
app.use((0, cors_1.default)());
app.use(express_1.default.json());
const requestTracker = new RequestTracker_1.RequestTracker();
const contentGenerator = new ContentGenerator_1.ContentGenerator();
const audioGenerator = new AudioGenerator_1.AudioGenerator();
const videoGenerator = new VideoGenerator_1.VideoGenerator();
const imageHandler = new ImageHandler_1.ImageHandler();
setInterval(() => {
    requestTracker.cleanOldRequests();
}, 3600000);
app.get("/", (_req, res) => {
    res.sendFile(path_1.default.join(__dirname, "../templates/index.html"));
});
app.get("/health", (_req, res) => {
    res.json({ status: "ok", pid: process.pid });
});
app.get("/api/models", async (_req, res) => {
    try {
        const models = audioGenerator.getAvailableModels();
        return res.json(models);
    }
    catch (error) {
        return res.status(500).json({ error: error.message });
    }
});
app.post("/api/generate", async (req, res) => {
    try {
        const { idea, format = "shorts", tts_model = "edge", voice, api_keys = {}, } = req.body;
        if (!idea) {
            return res.status(400).json({ error: "Video idea is required" });
        }
        if (format !== "shorts" && format !== "normal") {
            return res.status(400).json({ error: "Invalid video format" });
        }
        const availableModels = audioGenerator.getAvailableModels();
        if (!availableModels[tts_model]) {
            return res.status(400).json({ error: "Invalid TTS model" });
        }
        if (voice && !availableModels[tts_model].voices.includes(voice)) {
            return res
                .status(400)
                .json({ error: "Invalid voice for selected model" });
        }
        imageHandler.setFormat(format);
        videoGenerator.setFormat(format);
        const requestId = requestTracker.createRequest();
        generateContent(requestId, {
            idea,
            format,
            tts_model,
            voice: voice || undefined,
            api_keys,
        }).catch((error) => {
            console.error("Error in content generation:", error);
            requestTracker.updateRequest(requestId, {
                status: types_1.RequestStatus.FAILED,
                error: error.message,
            });
        });
        return res.status(202).json({
            request_id: requestId,
            status: "pending",
            message: "Generation started",
        });
    }
    catch (error) {
        return res.status(500).json({ error: error.message });
    }
});
app.get("/api/status/:requestId", (req, res) => {
    try {
        const { requestId } = req.params;
        const requestData = requestTracker.getRequest(requestId);
        if (!requestData) {
            return res.status(404).json({ error: "Request not found" });
        }
        const stageDescriptions = {
            pending: "Initializing...",
            generating_content: "Generating video script and content...",
            generating_audio: "Converting script to audio...",
            generating_images: "Creating background images...",
            generating_video: "Assembling final video...",
            completed: "Video generation completed!",
            failed: "Video generation failed.",
        };
        const response = {
            ...requestData,
            stage_description: stageDescriptions[requestData.status] || "",
            estimated_time_remaining: null,
        };
        return res.json(response);
    }
    catch (error) {
        return res.status(500).json({ error: error.message });
    }
});
app.get("/api/download/:requestId/:contentType/:filename", (req, res) => {
    try {
        const { requestId, contentType, filename } = req.params;
        const contentTypeMap = {
            video: "video",
            audio: "audio",
            script: "script",
            thumbnail: "video",
            image: "images",
        };
        if (!(contentType in contentTypeMap)) {
            return res.status(400).json({ error: "Invalid content type" });
        }
        const directory = path_1.default.join(process.cwd(), "contents", requestId, contentTypeMap[contentType]);
        let targetFilename = filename;
        if (contentType === "thumbnail") {
            const baseName = path_1.default.parse(filename).name;
            targetFilename = `${baseName}_thumbnail.jpg`;
        }
        const filePath = path_1.default.join(directory, targetFilename);
        const absFilePath = path_1.default.resolve(filePath);
        const absDirectory = path_1.default.resolve(directory);
        if (!absFilePath.startsWith(absDirectory)) {
            return res.status(403).json({ error: "Invalid file path" });
        }
        if (!fs_1.default.existsSync(absFilePath)) {
            return res.status(404).json({ error: "File not found" });
        }
        const mimeTypes = {
            video: "video/mp4",
            audio: "audio/mpeg",
            script: "text/plain",
            thumbnail: "image/jpeg",
            image: "image/jpeg",
        };
        res.setHeader("Content-Type", mimeTypes[contentType]);
        res.setHeader("Content-Disposition", `attachment; filename="${targetFilename}"`);
        return res.sendFile(absFilePath);
    }
    catch (error) {
        return res.status(500).json({ error: error.message });
    }
});
app.post("/api/prepare-video-data", async (req, res) => {
    try {
        const { idea, video_format = "shorts", tts_model = "edge", voice, api_keys = {}, } = req.body;
        if (!idea) {
            return res.status(400).json({ error: "No idea provided" });
        }
        const requestId = requestTracker.createRequest();
        requestTracker.updateRequest(requestId, {
            status: types_1.RequestStatus.PENDING,
        });
        const content = await contentGenerator.generateContent(idea, video_format, api_keys);
        requestTracker.updateRequest(requestId, {
            status: types_1.RequestStatus.GENERATING_CONTENT,
        });
        const audioPath = (await audioGenerator.generateAudio(content.script, requestId, {
            model: tts_model,
            voice: voice || undefined,
            apiKeys: api_keys,
        }));
        requestTracker.updateRequest(requestId, {
            status: types_1.RequestStatus.GENERATING_AUDIO,
        });
        const backgroundImages = await imageHandler.generateBackgroundImages(content.imagePrompts, requestId, api_keys);
        requestTracker.updateRequest(requestId, {
            status: types_1.RequestStatus.GENERATING_IMAGES,
        });
        videoGenerator.setFormat(video_format);
        const wordTimings = await videoGenerator.getPreciseWordTimings(audioPath, content.script);
        const responseData = {
            request_id: requestId,
            content,
            paths: {
                audio: audioPath,
                background_images: backgroundImages,
            },
            video_settings: {
                format: video_format,
                width: videoGenerator.WIDTH,
                height: videoGenerator.HEIGHT,
                duration: videoGenerator.DURATION,
            },
            timings: wordTimings,
            title: {
                text: content.title,
                position: {
                    x: "center",
                    y: Math.floor(videoGenerator.HEIGHT / 5),
                },
            },
        };
        requestTracker.updateRequest(requestId, {
            status: types_1.RequestStatus.COMPLETED,
            result: responseData,
        });
        return res.json(responseData);
    }
    catch (error) {
        console.error("Error in prepare-video-data:", error);
        return res.status(500).json({ error: error.message });
    }
});
app.delete("/api/content/:requestId", async (req, res) => {
    try {
        const { requestId } = req.params;
        console.log("\nDelete request - ID:", requestId);
        let success = false;
        const requestData = requestTracker.getRequest(requestId);
        if (requestData) {
            requestTracker.deleteRequest(requestId);
            success = true;
        }
        try {
            await deleteRequestDirectory(requestId);
            success = true;
        }
        catch (error) {
            if (error instanceof Error) {
                if (error.message.includes("ENOENT")) {
                    if (!success) {
                        return res.status(404).json({ error: "Content not found" });
                    }
                }
                else if (error.message.includes("EACCES")) {
                    return res
                        .status(403)
                        .json({ error: "Permission denied when deleting files" });
                }
                else if (!success) {
                    return res
                        .status(500)
                        .json({ error: `Error deleting files: ${error.message}` });
                }
            }
        }
        return res.json({
            message: "Content deleted successfully",
            request_id: requestId,
        });
    }
    catch (error) {
        console.error("Error in delete_content:", error);
        return res.status(500).json({ error: error.message });
    }
});
async function deleteRequestDirectory(requestId) {
    const contentsDir = path_1.default.join(process.cwd(), "contents");
    const directories = [
        path_1.default.join(contentsDir, requestId),
        path_1.default.join(contentsDir, "video", requestId),
        path_1.default.join(contentsDir, "audio", requestId),
        path_1.default.join(contentsDir, "images", requestId),
        path_1.default.join(contentsDir, "script", requestId),
    ];
    let deleted = false;
    for (const directory of directories) {
        if (fs_1.default.existsSync(directory)) {
            console.log("Deleting directory:", directory);
            await fs_1.default.promises.rm(directory, { recursive: true, force: true });
            console.log("Successfully deleted directory:", directory);
            deleted = true;
        }
    }
    if (!deleted) {
        console.log("No directories found for request ID:", requestId);
        throw new Error(`No content found for request ID: ${requestId}`);
    }
}
async function generateContent(requestId, options) {
    const { idea, format, tts_model, voice, api_keys } = options;
    try {
        requestTracker.updateRequest(requestId, {
            status: types_1.RequestStatus.GENERATING_CONTENT,
            progress: 10,
        });
        const content = await contentGenerator.generateContent(idea, format, api_keys);
        const scriptDir = path_1.default.join("contents", requestId, "script");
        fs_1.default.mkdirSync(scriptDir, { recursive: true });
        fs_1.default.writeFileSync(path_1.default.join(scriptDir, `${requestId}_original.txt`), content.script);
        requestTracker.updateRequest(requestId, {
            status: types_1.RequestStatus.GENERATING_AUDIO,
            progress: 30,
        });
        const audioResult = await audioGenerator.generateAudio(content.script, requestId, {
            model: tts_model,
            voice,
            outputDir: path_1.default.join("contents", requestId, "audio"),
            apiKeys: api_keys,
        });
        const audioPath = Array.isArray(audioResult) ? audioResult[0] : audioResult;
        requestTracker.updateRequest(requestId, {
            status: types_1.RequestStatus.GENERATING_IMAGES,
            progress: 40,
        });
        const prompts = await videoGenerator.generatePromptsWithOpenAI(content.script, api_keys);
        if (!prompts || prompts.length === 0) {
            throw new Error("Failed to generate image prompts");
        }
        const imagePaths = await imageHandler.generateBackgroundImages(prompts, requestId, {
            outputDir: path_1.default.join("contents", requestId, "images"),
            apiKeys: api_keys,
            imageUrls: content.imageUrls,
        });
        if (!imagePaths || imagePaths.length === 0) {
            throw new Error("Failed to generate background images");
        }
        requestTracker.updateRequest(requestId, {
            status: types_1.RequestStatus.GENERATING_VIDEO,
            progress: 70,
        });
        const videoResult = await videoGenerator.generateVideo(audioPath, {
            title: content.title,
            script: content.script,
        }, requestId, imagePaths, (progress) => {
            console.log(`Video generation progress: ${progress}%`);
        });
        requestTracker.updateRequest(requestId, {
            status: types_1.RequestStatus.COMPLETED,
            progress: 100,
            result: {
                video: {
                    filename: path_1.default.basename(videoResult.videoPath),
                    url: `/api/download/${requestId}/video/${path_1.default.basename(videoResult.videoPath)}`,
                },
                thumbnail: {
                    filename: path_1.default.basename(videoResult.thumbnailPath),
                    url: `/api/download/${requestId}/thumbnail/${path_1.default.basename(videoResult.thumbnailPath)}`,
                },
                script: {
                    original: `${requestId}_original.txt`,
                    final: path_1.default.basename(videoResult.scriptPath),
                    url: `/api/download/${requestId}/script/${path_1.default.basename(videoResult.scriptPath)}`,
                },
                content: {
                    title: content.title,
                    script: content.script,
                    hashtags: content.hashtags,
                },
                metadata: {
                    format,
                    tts_model,
                    voice,
                },
            },
        });
    }
    catch (error) {
        console.error("Error in content generation:", error);
        requestTracker.updateRequest(requestId, {
            status: types_1.RequestStatus.FAILED,
            error: error.message,
        });
        throw error;
    }
}
app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});
//# sourceMappingURL=app.js.map
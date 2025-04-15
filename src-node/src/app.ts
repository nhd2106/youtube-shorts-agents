import express from "express";
import cors from "cors";
import path from "path";
import fs from "fs";
import { config } from "dotenv";
import { RequestTracker } from "./services/RequestTracker";
import { ContentGenerator } from "./services/ContentGenerator";
import { AudioGenerator } from "./services/AudioGenerator";
import { VideoGenerator } from "./services/VideoGenerator";
import { ImageHandler } from "./services/ImageHandler";
import { RequestStatus } from "./types";

// Load environment variables
config();

// Parse command line arguments
const args = process.argv.slice(2);
const portArg = args.find((arg) => arg.startsWith("--port="));
const PORT = portArg
  ? parseInt(portArg.split("=")[1], 10)
  : process.env.PORT
  ? parseInt(process.env.PORT, 10)
  : 3000;

// Log startup information
console.log(`Starting YouTube Shorts Agent server on port ${PORT}`);
console.log(`Process ID: ${process.pid}`);
console.log(`Working directory: ${process.cwd()}`);

const app = express();
app.use(cors());
app.use(express.json());

// Initialize services
const requestTracker = new RequestTracker();
const contentGenerator = new ContentGenerator();
const audioGenerator = new AudioGenerator();
const videoGenerator = new VideoGenerator();
const imageHandler = new ImageHandler();

// Start background task to clean old requests
setInterval(() => {
  requestTracker.cleanOldRequests();
}, 3600000); // Clean every hour

// Routes
app.get("/", (_req, res) => {
  res.sendFile(path.join(__dirname, "../templates/index.html"));
});

// Add a health check endpoint
app.get("/health", (_req, res) => {
  res.json({ status: "ok", pid: process.pid });
});

app.get("/api/models", async (_req, res) => {
  try {
    const models = audioGenerator.getAvailableModels();
    return res.json(models);
  } catch (error) {
    return res.status(500).json({ error: (error as Error).message });
  }
});

app.post("/api/generate", async (req, res) => {
  try {
    const {
      idea,
      format = "shorts",
      tts_model = "edge",
      voice,
      api_keys = {},
    } = req.body;

    if (!idea) {
      return res.status(400).json({ error: "Video idea is required" });
    }

    if (format !== "shorts" && format !== "normal") {
      return res.status(400).json({ error: "Invalid video format" });
    }

    // Validate TTS model and voice
    const availableModels = audioGenerator.getAvailableModels();
    if (!availableModels[tts_model]) {
      return res.status(400).json({ error: "Invalid TTS model" });
    }

    if (voice && !availableModels[tts_model].voices.includes(voice)) {
      return res
        .status(400)
        .json({ error: "Invalid voice for selected model" });
    }

    // Set format for image and video generation
    imageHandler.setFormat(format);
    videoGenerator.setFormat(format);

    // Create request and start generation in background
    const requestId = requestTracker.createRequest();

    // Start async generation
    generateContent(requestId, {
      idea,
      format,
      tts_model,
      voice: voice || undefined,
      api_keys,
    }).catch((error) => {
      console.error("Error in content generation:", error);
      requestTracker.updateRequest(requestId, {
        status: RequestStatus.FAILED,
        error: error.message,
      });
    });

    // Return request ID immediately
    return res.status(202).json({
      request_id: requestId,
      status: "pending",
      message: "Generation started",
    });
  } catch (error) {
    return res.status(500).json({ error: (error as Error).message });
  }
});

app.get("/api/status/:requestId", (req, res) => {
  try {
    const { requestId } = req.params;
    const requestData = requestTracker.getRequest(requestId);

    if (!requestData) {
      return res.status(404).json({ error: "Request not found" });
    }

    // Add stage descriptions for better UX
    const stageDescriptions: Record<string, string> = {
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
      estimated_time_remaining: null, // Could be implemented based on average completion times
    };

    return res.json(response);
  } catch (error) {
    return res.status(500).json({ error: (error as Error).message });
  }
});

app.get("/api/download/:requestId/:contentType/:filename", (req, res) => {
  try {
    const { requestId, contentType, filename } = req.params;

    // Map content types to directories
    const contentTypeMap: Record<string, string> = {
      video: "video",
      audio: "audio",
      script: "script",
      thumbnail: "video",
      image: "images",
    };

    if (!(contentType in contentTypeMap)) {
      return res.status(400).json({ error: "Invalid content type" });
    }

    // Get the request-specific directory for the content type
    const directory = path.join(
      process.cwd(),
      "contents",
      requestId,
      contentTypeMap[contentType]
    );

    // Handle thumbnail files
    let targetFilename = filename;
    if (contentType === "thumbnail") {
      // Remove any existing extension and add _thumbnail.jpg
      const baseName = path.parse(filename).name;
      targetFilename = `${baseName}_thumbnail.jpg`;
    }

    const filePath = path.join(directory, targetFilename);

    // Verify the file exists and is within the allowed directory
    const absFilePath = path.resolve(filePath);
    const absDirectory = path.resolve(directory);

    if (!absFilePath.startsWith(absDirectory)) {
      return res.status(403).json({ error: "Invalid file path" });
    }

    if (!fs.existsSync(absFilePath)) {
      return res.status(404).json({ error: "File not found" });
    }

    // Set appropriate MIME type based on content type
    const mimeTypes: Record<string, string> = {
      video: "video/mp4",
      audio: "audio/mpeg",
      script: "text/plain",
      thumbnail: "image/jpeg",
      image: "image/jpeg",
    };

    res.setHeader("Content-Type", mimeTypes[contentType]);
    res.setHeader(
      "Content-Disposition",
      `attachment; filename="${targetFilename}"`
    );
    return res.sendFile(absFilePath);
  } catch (error) {
    return res.status(500).json({ error: (error as Error).message });
  }
});

app.post("/api/prepare-video-data", async (req, res) => {
  try {
    const {
      idea,
      video_format = "shorts",
      tts_model = "edge",
      voice,
      api_keys = {},
    } = req.body;

    if (!idea) {
      return res.status(400).json({ error: "No idea provided" });
    }

    // Create new request
    const requestId = requestTracker.createRequest();

    // Set initial status
    requestTracker.updateRequest(requestId, {
      status: RequestStatus.PENDING,
    });

    // Generate content with API keys
    const content = await contentGenerator.generateContent(
      idea,
      video_format,
      api_keys
    );
    requestTracker.updateRequest(requestId, {
      status: RequestStatus.GENERATING_CONTENT,
    });

    // Generate audio with API keys
    const audioPath = (await audioGenerator.generateAudio(
      content.script,
      requestId,
      {
        model: tts_model,
        voice: voice || undefined,
        apiKeys: api_keys,
      }
    )) as any;
    requestTracker.updateRequest(requestId, {
      status: RequestStatus.GENERATING_AUDIO,
    });

    // Generate images with API keys
    const backgroundImages = await imageHandler.generateBackgroundImages(
      content.imagePrompts,
      requestId,
      api_keys
    );
    requestTracker.updateRequest(requestId, {
      status: RequestStatus.GENERATING_IMAGES,
    });

    // Set video format and get dimensions
    videoGenerator.setFormat(video_format);

    // Get word timings for captions
    const wordTimings = await videoGenerator.getPreciseWordTimings(
      audioPath,
      content.script
    );

    // Prepare response data
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
          y: Math.floor(videoGenerator.HEIGHT / 5), // 1/5 from top
        },
      },
    };

    requestTracker.updateRequest(requestId, {
      status: RequestStatus.COMPLETED,
      result: responseData,
    });

    return res.json(responseData);
  } catch (error) {
    console.error("Error in prepare-video-data:", error);
    return res.status(500).json({ error: (error as Error).message });
  }
});

app.delete("/api/content/:requestId", async (req, res) => {
  try {
    const { requestId } = req.params;
    console.log("\nDelete request - ID:", requestId);
    let success = false;

    // Try to delete from request tracker if it exists
    const requestData = requestTracker.getRequest(requestId);
    if (requestData) {
      requestTracker.deleteRequest(requestId);
      success = true;
    }

    // Try to delete files regardless of request tracker status
    try {
      await deleteRequestDirectory(requestId);
      success = true;
    } catch (error) {
      if (error instanceof Error) {
        if (error.message.includes("ENOENT")) {
          // Directory not found
          if (!success) {
            return res.status(404).json({ error: "Content not found" });
          }
        } else if (error.message.includes("EACCES")) {
          // Permission error
          return res
            .status(403)
            .json({ error: "Permission denied when deleting files" });
        } else if (!success) {
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
  } catch (error) {
    console.error("Error in delete_content:", error);
    return res.status(500).json({ error: (error as Error).message });
  }
});

// Helper function to delete request directory
async function deleteRequestDirectory(requestId: string): Promise<void> {
  const contentsDir = path.join(process.cwd(), "contents");

  // List of directories to check and delete
  const directories = [
    path.join(contentsDir, requestId), // Main request directory
    path.join(contentsDir, "video", requestId), // Video directory (includes thumbnails)
    path.join(contentsDir, "audio", requestId), // Audio directory
    path.join(contentsDir, "images", requestId), // Images directory
    path.join(contentsDir, "script", requestId), // Script directory
  ];

  let deleted = false;
  for (const directory of directories) {
    if (fs.existsSync(directory)) {
      console.log("Deleting directory:", directory);
      await fs.promises.rm(directory, { recursive: true, force: true });
      console.log("Successfully deleted directory:", directory);
      deleted = true;
    }
  }

  if (!deleted) {
    console.log("No directories found for request ID:", requestId);
    throw new Error(`No content found for request ID: ${requestId}`);
  }
}

// Helper function to generate content
async function generateContent(
  requestId: string,
  options: {
    idea: string;
    format: string;
    tts_model: string;
    voice?: string;
    api_keys: Record<string, string>;
  }
): Promise<void> {
  const { idea, format, tts_model, voice, api_keys } = options;

  try {
    // Update status to generating content
    requestTracker.updateRequest(requestId, {
      status: RequestStatus.GENERATING_CONTENT,
      progress: 10,
    });

    // Generate content
    const content = await contentGenerator.generateContent(
      idea,
      format,
      api_keys
    );

    // Save initial script
    const scriptDir = path.join("contents", requestId, "script");
    fs.mkdirSync(scriptDir, { recursive: true });
    fs.writeFileSync(
      path.join(scriptDir, `${requestId}_original.txt`),
      content.script
    );

    // Generate audio
    requestTracker.updateRequest(requestId, {
      status: RequestStatus.GENERATING_AUDIO,
      progress: 30,
    });

    const audioResult = await audioGenerator.generateAudio(
      content.script,
      requestId,
      {
        model: tts_model,
        voice,
        outputDir: path.join("contents", requestId, "audio"),
        apiKeys: api_keys,
      }
    );

    // Extract audio path from result
    const audioPath = Array.isArray(audioResult) ? audioResult[0] : audioResult;

    // Generate image prompts and images
    requestTracker.updateRequest(requestId, {
      status: RequestStatus.GENERATING_IMAGES,
      progress: 40,
    });

    const prompts = await videoGenerator.generatePromptsWithOpenAI(
      content.script,
      api_keys
    );

    if (!prompts || prompts.length === 0) {
      throw new Error("Failed to generate image prompts");
    }

    const imagePaths = await imageHandler.generateBackgroundImages(
      prompts,
      requestId,
      {
        outputDir: path.join("contents", requestId, "images"),
        apiKeys: api_keys,
        imageUrls: content.imageUrls,
      }
    );

    if (!imagePaths || imagePaths.length === 0) {
      throw new Error("Failed to generate background images");
    }

    // Generate video
    requestTracker.updateRequest(requestId, {
      status: RequestStatus.GENERATING_VIDEO,
      progress: 70,
    });

    const videoResult = await videoGenerator.generateVideo(
      audioPath,
      {
        title: content.title,
        script: content.script,
      },
      requestId,
      imagePaths,
      (progress: number) => {
        console.log(`Video generation progress: ${progress}%`);
      }
    );

    // Update request with final result
    requestTracker.updateRequest(requestId, {
      status: RequestStatus.COMPLETED,
      progress: 100,
      result: {
        video: {
          filename: path.basename(videoResult.videoPath),
          url: `/api/download/${requestId}/video/${path.basename(
            videoResult.videoPath
          )}`,
        },
        thumbnail: {
          filename: path.basename(videoResult.thumbnailPath),
          url: `/api/download/${requestId}/thumbnail/${path.basename(
            videoResult.thumbnailPath
          )}`,
        },
        script: {
          original: `${requestId}_original.txt`,
          final: path.basename(videoResult.scriptPath),
          url: `/api/download/${requestId}/script/${path.basename(
            videoResult.scriptPath
          )}`,
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
  } catch (error) {
    console.error("Error in content generation:", error);
    requestTracker.updateRequest(requestId, {
      status: RequestStatus.FAILED,
      error: (error as Error).message,
    });
    throw error;
  }
}

// Start the server
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});

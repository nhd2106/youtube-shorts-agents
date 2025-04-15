"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ImageHandler = void 0;
const path_1 = __importDefault(require("path"));
const fs_1 = __importDefault(require("fs"));
const uuid_1 = require("uuid");
const sharp_1 = __importDefault(require("sharp"));
const axios_1 = __importDefault(require("axios"));
const together_ai_1 = __importDefault(require("together-ai"));
class ImageHandler {
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
        this.currentFormat = null;
        this.width = null;
        this.height = null;
        this.defaultOutputDir = path_1.default.join(process.cwd(), "contents", "images");
        this.togetherClient = null;
        fs_1.default.mkdirSync(this.defaultOutputDir, { recursive: true });
    }
    initTogetherClient(apiKey) {
        if (!apiKey) {
            throw new Error("Together AI API key is required for image generation");
        }
        this.togetherClient = new together_ai_1.default({ apiKey });
    }
    setFormat(formatType) {
        if (!this.videoFormats[formatType]) {
            throw new Error(`Invalid format type. Choose from: ${Object.keys(this.videoFormats).join(", ")}`);
        }
        if (this.currentFormat !== formatType) {
            this.currentFormat = formatType;
            this.width = this.videoFormats[formatType].width;
            this.height = this.videoFormats[formatType].height;
            console.log(`Image format set to ${formatType} with dimensions ${this.width}x${this.height}`);
        }
        if (!this.width || !this.height) {
            throw new Error("Format must be set before generating images");
        }
    }
    async delay(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }
    async generateBackgroundImages(prompts, requestId, options = {}) {
        try {
            const { outputDir = path_1.default.join("contents", requestId, "images"), apiKeys = {}, imageUrls = [], } = options;
            if (!this.currentFormat || !this.width || !this.height) {
                throw new Error("Format must be set before generating images");
            }
            fs_1.default.mkdirSync(outputDir, { recursive: true });
            const imagePaths = [];
            if (imageUrls.length > 0) {
                console.log(`Found ${imageUrls.length} images from URLs, attempting to download...`);
                const downloadPromises = imageUrls.map((url) => this.downloadAndProcessImage(url, outputDir));
                const downloadResults = await Promise.all(downloadPromises);
                imagePaths.push(...downloadResults.filter((path) => path !== null));
                console.log(`Successfully downloaded ${imagePaths.length} images from URLs`);
                const requiredImages = this.currentFormat === "shorts" ? 9 : 18;
                if (imagePaths.length >= requiredImages) {
                    console.log(`Got enough images from URLs (${imagePaths.length}), skipping AI generation`);
                    return imagePaths;
                }
                console.log(`Not enough images from URLs (${imagePaths.length}), generating ${requiredImages - imagePaths.length} more...`);
            }
            if (prompts.length > 0) {
                if (!apiKeys.together) {
                    throw new Error("Together AI API key is required for image generation");
                }
                this.initTogetherClient(apiKeys.together);
                const batchSize = 3;
                for (let i = 0; i < prompts.length; i += batchSize) {
                    if (i > 0) {
                        console.log("Waiting 30 seconds before next batch to respect rate limit...");
                        await this.delay(30000);
                    }
                    const batchPrompts = prompts.slice(i, i + batchSize);
                    console.log(`Processing batch ${Math.floor(i / batchSize) + 1} of ${Math.ceil(prompts.length / batchSize)}`);
                    const batchPromises = batchPrompts.map((prompt, index) => this.generateImage(prompt, i + index, prompts.length, outputDir));
                    const batchResults = await Promise.all(batchPromises);
                    imagePaths.push(...batchResults.filter((path) => path !== null));
                }
            }
            if (imagePaths.length === 0) {
                const defaultImagePath = path_1.default.join(outputDir, "default.jpg");
                await (0, sharp_1.default)({
                    create: {
                        width: this.width,
                        height: this.height,
                        channels: 3,
                        background: { r: 0, g: 0, b: 0 },
                    },
                })
                    .jpeg()
                    .toFile(defaultImagePath);
                imagePaths.push(defaultImagePath);
            }
            return imagePaths;
        }
        catch (error) {
            console.error("Error in image generation:", error);
            throw error;
        }
    }
    async generateImage(prompt, index, total, outputDir) {
        try {
            if (!this.currentFormat || !this.width || !this.height) {
                throw new Error("Video format not set");
            }
            const widthSteps = 64;
            const heightSteps = 64;
            const width = this.currentFormat === "shorts" ? 9 * widthSteps : 16 * widthSteps;
            const height = this.currentFormat === "shorts" ? 16 * heightSteps : 9 * heightSteps;
            console.log(`Generating ${this.currentFormat} format image ${index + 1}/${total}`);
            const response = await this.generateImageWithTogetherAI(prompt, width, height);
            if (!response) {
                console.error("No valid response data received");
                return null;
            }
            const outputPath = path_1.default.join(outputDir, `generated_image_${index}.jpg`);
            await this.processAndSaveImage(response, outputPath);
            console.log(`Saved generated image to: ${outputPath}`);
            return outputPath;
        }
        catch (error) {
            console.error("Error generating image:", error);
            return null;
        }
    }
    async generateImageWithTogetherAI(prompt, width, height) {
        try {
            if (!this.togetherClient) {
                throw new Error("Together AI client not initialized");
            }
            const response = await this.togetherClient.images.create({
                model: "black-forest-labs/FLUX.1-schnell-Free",
                prompt: prompt,
                width: width,
                height: height,
                steps: 1,
                n: 1,
                response_format: "b64_json",
            });
            if (!response?.data?.[0]?.b64_json) {
                throw new Error("Invalid response from Together AI");
            }
            return Buffer.from(response.data[0].b64_json, "base64");
        }
        catch (error) {
            console.error("Together AI API error:", error);
            return null;
        }
    }
    async processAndSaveImage(imageBuffer, outputPath) {
        if (!imageBuffer) {
            throw new Error("No image data provided");
        }
        const image = (0, sharp_1.default)(imageBuffer);
        await this.resizeAndCrop(image, outputPath);
    }
    async downloadAndProcessImage(url, outputDir, outputPath) {
        try {
            if (!outputPath) {
                const filename = `${(0, uuid_1.v4)()}.jpg`;
                outputPath = path_1.default.join(outputDir, filename);
            }
            fs_1.default.mkdirSync(path_1.default.dirname(outputPath), { recursive: true });
            const response = await axios_1.default.get(url, {
                responseType: "arraybuffer",
                headers: {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                },
                timeout: 10000,
            });
            const imageBuffer = Buffer.from(response.data);
            const image = (0, sharp_1.default)(imageBuffer);
            const metadata = await image.metadata();
            if (!metadata.width ||
                !metadata.height ||
                metadata.width < 300 ||
                metadata.height < 300) {
                console.log(`Image too small: ${metadata.width}x${metadata.height}`);
                return null;
            }
            await this.resizeAndCrop(image, outputPath);
            console.log(`Successfully processed image: ${url}`);
            console.log(`Original size: ${metadata.width}x${metadata.height}`);
            return outputPath;
        }
        catch (error) {
            console.error(`Error processing image from ${url}:`, error);
            return null;
        }
    }
    async resizeAndCrop(image, outputPath) {
        if (!this.width || !this.height) {
            throw new Error("Video dimensions not set");
        }
        const metadata = await image.metadata();
        if (!metadata.width || !metadata.height) {
            throw new Error("Unable to get image dimensions");
        }
        const targetRatio = this.width / this.height;
        const imageRatio = metadata.width / metadata.height;
        let resizeOptions = {
            width: this.width,
            height: this.height,
            fit: sharp_1.default.fit.cover,
            position: sharp_1.default.strategy.attention,
        };
        if (Math.abs(imageRatio - targetRatio) > 0.01) {
            if (imageRatio > targetRatio) {
                resizeOptions.width = Math.round(metadata.height * targetRatio);
                resizeOptions.height = metadata.height;
            }
            else {
                resizeOptions.width = metadata.width;
                resizeOptions.height = Math.round(metadata.width / targetRatio);
            }
        }
        await image.resize(resizeOptions).jpeg({ quality: 95 }).toFile(outputPath);
    }
}
exports.ImageHandler = ImageHandler;
//# sourceMappingURL=ImageHandler.js.map
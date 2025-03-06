import path from "path";
import fs from "fs";
import { v4 as uuidv4 } from "uuid";
import sharp from "sharp";
import axios from "axios";
import { VideoFormat } from "../types";
import TogetherAI from "together-ai";

export class ImageHandler {
  private videoFormats: Record<string, VideoFormat>;
  private currentFormat: string | null;
  private width: number | null;
  private height: number | null;
  private defaultOutputDir: string;
  private togetherClient: any | null;

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
    this.defaultOutputDir = path.join(process.cwd(), "contents", "images");
    this.togetherClient = null;

    // Create default output directory
    fs.mkdirSync(this.defaultOutputDir, { recursive: true });
  }

  private initTogetherClient(apiKey: string): void {
    if (!apiKey) {
      throw new Error("Together AI API key is required for image generation");
    }
    // Initialize Together AI client (implementation depends on their SDK)
    this.togetherClient = new TogetherAI({ apiKey });
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
        `Image format set to ${formatType} with dimensions ${this.width}x${this.height}`
      );
    }

    if (!this.width || !this.height) {
      throw new Error("Format must be set before generating images");
    }
  }

  private async delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async generateBackgroundImages(
    prompts: string[],
    requestId: string,
    options: {
      outputDir?: string;
      apiKeys?: Record<string, string>;
      imageUrls?: string[];
    } = {}
  ): Promise<string[]> {
    try {
      const {
        outputDir = path.join("contents", requestId, "images"),
        apiKeys = {},
        imageUrls = [],
      } = options;

      if (!this.currentFormat || !this.width || !this.height) {
        throw new Error("Format must be set before generating images");
      }

      fs.mkdirSync(outputDir, { recursive: true });
      const imagePaths: string[] = [];

      // If we have image URLs, try to download them first
      if (imageUrls.length > 0) {
        console.log(
          `Found ${imageUrls.length} images from URLs, attempting to download...`
        );
        const downloadPromises = imageUrls.map((url) =>
          this.downloadAndProcessImage(url, outputDir)
        );
        const downloadResults = await Promise.all(downloadPromises);
        imagePaths.push(
          ...downloadResults.filter((path): path is string => path !== null)
        );
        console.log(
          `Successfully downloaded ${imagePaths.length} images from URLs`
        );

        // If we have enough images from URLs, return them
        const requiredImages = this.currentFormat === "shorts" ? 9 : 18;
        if (imagePaths.length >= requiredImages) {
          console.log(
            `Got enough images from URLs (${imagePaths.length}), skipping AI generation`
          );
          return imagePaths;
        }

        console.log(
          `Not enough images from URLs (${imagePaths.length}), generating ${
            requiredImages - imagePaths.length
          } more...`
        );
      }

      // Only generate AI images if we need more
      if (prompts.length > 0) {
        if (!apiKeys.together) {
          throw new Error(
            "Together AI API key is required for image generation"
          );
        }

        this.initTogetherClient(apiKeys.together);

        // Process prompts in batches of 3 with delay between batches
        const batchSize = 3;
        for (let i = 0; i < prompts.length; i += batchSize) {
          // Add delay between batches to respect rate limit (6 images per minute)
          if (i > 0) {
            console.log(
              "Waiting 30 seconds before next batch to respect rate limit..."
            );
            await this.delay(30000); // Wait 30 seconds between batches
          }

          const batchPrompts = prompts.slice(i, i + batchSize);
          console.log(
            `Processing batch ${Math.floor(i / batchSize) + 1} of ${Math.ceil(
              prompts.length / batchSize
            )}`
          );

          const batchPromises = batchPrompts.map((prompt, index) =>
            this.generateImage(prompt, i + index, prompts.length, outputDir)
          );
          const batchResults = await Promise.all(batchPromises);
          imagePaths.push(
            ...batchResults.filter((path): path is string => path !== null)
          );
        }
      }

      // Ensure we have at least one image
      if (imagePaths.length === 0) {
        // Create a default black image if no images were generated
        const defaultImagePath = path.join(outputDir, "default.jpg");
        await sharp({
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
    } catch (error) {
      console.error("Error in image generation:", error);
      throw error; // Re-throw the error instead of returning empty array
    }
  }

  private async generateImage(
    prompt: string,
    index: number,
    total: number,
    outputDir: string
  ): Promise<string | null> {
    try {
      if (!this.currentFormat || !this.width || !this.height) {
        throw new Error("Video format not set");
      }

      // Calculate dimensions based on format
      const widthSteps = 64;
      const heightSteps = 64;
      const width =
        this.currentFormat === "shorts" ? 9 * widthSteps : 16 * widthSteps;
      const height =
        this.currentFormat === "shorts" ? 16 * heightSteps : 9 * heightSteps;

      console.log(
        `Generating ${this.currentFormat} format image ${index + 1}/${total}`
      );

      // This is a placeholder for the actual Together AI API call
      const response = await this.generateImageWithTogetherAI(
        prompt,
        width,
        height
      );

      if (!response) {
        console.error("No valid response data received");
        return null;
      }

      // Process and save the image
      const outputPath = path.join(outputDir, `generated_image_${index}.jpg`);
      await this.processAndSaveImage(response, outputPath);

      console.log(`Saved generated image to: ${outputPath}`);
      return outputPath;
    } catch (error) {
      console.error("Error generating image:", error);
      return null;
    }
  }

  private async generateImageWithTogetherAI(
    prompt: string,
    width: number,
    height: number
  ): Promise<Buffer | null> {
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
    } catch (error) {
      console.error("Together AI API error:", error);
      return null;
    }
  }

  private async processAndSaveImage(
    imageBuffer: Buffer | null,
    outputPath: string
  ): Promise<void> {
    if (!imageBuffer) {
      throw new Error("No image data provided");
    }
    const image = sharp(imageBuffer);
    await this.resizeAndCrop(image, outputPath);
  }

  async downloadAndProcessImage(
    url: string,
    outputDir: string,
    outputPath?: string
  ): Promise<string | null> {
    try {
      if (!outputPath) {
        const filename = `${uuidv4()}.jpg`;
        outputPath = path.join(outputDir, filename);
      }

      fs.mkdirSync(path.dirname(outputPath), { recursive: true });

      const response = await axios.get(url, {
        responseType: "arraybuffer",
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        },
        timeout: 10000,
      });

      const imageBuffer = Buffer.from(response.data);

      // Process image with sharp
      const image = sharp(imageBuffer);
      const metadata = await image.metadata();

      if (
        !metadata.width ||
        !metadata.height ||
        metadata.width < 300 ||
        metadata.height < 300
      ) {
        console.log(`Image too small: ${metadata.width}x${metadata.height}`);
        return null;
      }

      // Resize and crop to match video dimensions
      await this.resizeAndCrop(image, outputPath);

      console.log(`Successfully processed image: ${url}`);
      console.log(`Original size: ${metadata.width}x${metadata.height}`);
      return outputPath;
    } catch (error) {
      console.error(`Error processing image from ${url}:`, error);
      return null;
    }
  }

  private async resizeAndCrop(
    image: sharp.Sharp,
    outputPath: string
  ): Promise<void> {
    if (!this.width || !this.height) {
      throw new Error("Video dimensions not set");
    }

    const metadata = await image.metadata();
    if (!metadata.width || !metadata.height) {
      throw new Error("Unable to get image dimensions");
    }

    const targetRatio = this.width / this.height;
    const imageRatio = metadata.width / metadata.height;

    let resizeOptions: sharp.ResizeOptions = {
      width: this.width,
      height: this.height,
      fit: sharp.fit.cover,
      position: sharp.strategy.attention,
    };

    if (Math.abs(imageRatio - targetRatio) > 0.01) {
      if (imageRatio > targetRatio) {
        // Image is wider than needed
        resizeOptions.width = Math.round(metadata.height * targetRatio);
        resizeOptions.height = metadata.height;
      } else {
        // Image is taller than needed
        resizeOptions.width = metadata.width;
        resizeOptions.height = Math.round(metadata.width / targetRatio);
      }
    }

    await image.resize(resizeOptions).jpeg({ quality: 95 }).toFile(outputPath);
  }
}

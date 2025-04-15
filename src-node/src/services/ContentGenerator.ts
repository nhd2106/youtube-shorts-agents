import { OpenAI } from "openai";
import axios from "axios";
import * as cheerio from "cheerio";
import { URL } from "url";
import { Content } from "../types";
import path from "path";
import fs from "fs";

interface ExtractedContent {
  title: string;
  content: string;
  images?: string[];
}

export class ContentGenerator {
  private client: OpenAI | null;
  private headers: Record<string, string>;

  constructor() {
    this.client = null;
    this.headers = {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
      Accept:
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
      "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
      "Accept-Encoding": "gzip, deflate",
      "Cache-Control": "no-cache",
      Pragma: "no-cache",
    };
  }

  private initClient(apiKeys: Record<string, string>): void {
    if (!apiKeys.openai) {
      throw new Error("OpenAI API key is required");
    }
    this.client = new OpenAI({ apiKey: apiKeys.openai });
  }

  async generateContent(
    idea: string,
    videoFormat: string = "shorts",
    apiKeys: Record<string, string> = {}
  ): Promise<Content> {
    let mainIdea = idea;
    if (idea.includes("https://")) {
      const url = RegExp(/https?:\/\/[^\s]+/);
      const urlMatch = idea.match(url);
      if (urlMatch) {
        const extracted = await this.extractContentFromUrl(urlMatch[0]);
        mainIdea += `\n\n${extracted.content}`;
      }
    }
    try {
      if (!apiKeys) {
        throw new Error("API keys are required");
      }

      // Initialize OpenAI client
      this.initClient(apiKeys);

      // Define format specifications
      const formatSpecs = {
        shorts: {
          type: "shorts",
          duration: "70s",
          scriptLength: "70 - 85 seconds",
          style: "energetic and engaging",
          wordCount: "350-400 words",
        },
        normal: {
          type: "normal",
          duration: "5-7 minutes",
          scriptLength: "5-7 minutes",
          style: "detailed and comprehensive",
          wordCount: "5000-6000 words",
        },
      };

      if (!(videoFormat in formatSpecs)) {
        throw new Error(
          `Invalid video format. Choose from: ${Object.keys(formatSpecs).join(
            ", "
          )}`
        );
      }

      const formatSpec = formatSpecs[videoFormat as keyof typeof formatSpecs];
      console.log(formatSpec, videoFormat);
      // Generate content with OpenAI
      const response = await this.client!.chat.completions.create({
        model: "gpt-4o-mini",
        messages: [
          {
            role: "system",
            content: this.getSystemPrompt(formatSpec),
          },
          {
            role: "user",
            content: mainIdea,
          },
        ],
        temperature: 0.7,
      });

      // Parse the content
      const content = this.parseContent(
        response.choices[0].message.content || "",
        formatSpec
      );

      return content;
    } catch (error) {
      console.error("Error generating content:", error);
      throw error;
    }
  }

  private getSystemPrompt(formatSpec: {
    type: string;
    duration: string;
    scriptLength: string;
    style: string;
    wordCount: string;
  }): string {
    console.log(formatSpec.wordCount);
    return `You are a creative content specialist focused on creating engaging ${formatSpec.type} videos.
You must respond in this exact format:
TITLE: [attention-grabbing title]
SCRIPT: [engaging script]
HASHTAGS: [relevant hashtags]

Guidelines for content creation:
1. Title Creation:
    - Ensure the title language matches the user input
    - Craft an attention-grabbing, unique title that sparks curiosity
    - Use relevant keywords for better discoverability
    - Keep it clear, concise, and compelling
    - Avoid clickbait - ensure the title accurately reflects content

2. Script rules:
    - Content Type Guidelines:
        • Historical: Include vivid storytelling elements to make dates and locations more engaging
        • Narrative: Focus on building relatable characters and a compelling plot
        • Factual: Use intriguing hooks to capture attention early on
        • Tutorial: Include interactive elements or visuals to aid understanding
        • Opinion: Balance opinions with compelling arguments and counterpoints to stimulate thought
    - Reference Guidelines:
        • when user paste url, you need Extract detailed information from the following article, including specific numbers, times, and key events:
            1. The main topic or purpose of the content.
            2. Key details, including dates, numbers, or statistics mentioned.
            3. Specific events, incidents, or actions described, if applicable.
            4. Any insights, arguments, or conclusions presented by the author.
            5. Notable quotes or statements from the text.
            6. Other relevant details that contribute to understanding the content.
            7. In case of user input has url, you need to extract detailed information from the url do not fabricate stories
            Provide a clear and concise summary of the extracted information, structured for readability.
        • Encourage the use of visuals or infographics when extracting detailed information
        • Summarize key points in bullet form for easier readability and retention
    - Content Requirements:
        • Consistently match the input language
        • don't seperate numbers by comma or dot, keep them together
        • Focus solely on the requested topic
        • Target length: ${formatSpec.duration} for a ${formatSpec.scriptLength} video
        • Keep the tone ${formatSpec.style}
        • Maintain a consistent tone that aligns with the intended audience
        • Use storytelling techniques such as anecdotes or metaphors
        • For normal format: Include detailed examples, case studies, or real-world applications
        • For shorts: Keep it concise and immediately engaging, use punchy language and dynamic visuals
        • Conclude with: in English "If you found this helpful, like and subscribe for more!"  or in Vietnamese "Nếu bạn thấy hay, đừng quên bấm like và đăng ký để ủng hộ kênh" (Choose one based on the user input language)
    - Storytelling Framework - Select ONE:
        • Hero's Journey: Challenge → Struggle → Triumph
        • 7-Second Hook: Grab attention in the first 7 seconds
        • Problem-Solution-Benefit Structure
        • 5-Why Analysis: Deep dive into root causes
        • Dual-Perspective Story: Before/After format
        • 10-Second Engagement Rule
        • Rhythmic/Rhyming Pattern for memorability
        • Experiment with different frameworks to see which resonates best
        • Use the 7-Second Hook to grab attention immediately
    * Remember: Language must match with the user input language

3. Hashtag Strategy:
    - Blend English and topic-specific hashtags
    - Include trending, relevant tags
    - Ensure hashtag relevance to content
    - Optimal mix: 60% topic-specific, 40% general engagement
    - Regularly update hashtags to include trending topics
    - Analyze engagement metrics to refine hashtag usage

4. Quality Standards:
    - Prioritize accuracy and current information
    - Maintain educational or entertainment value
    - Focus on audience engagement and value delivery
    - Keep content concise and impactful
    - Avoid filler content or unnecessary details
    - For normal format: Include supporting details, examples, and deeper analysis
    - For shorts: Focus on key points and immediate value
    - Incorporate user feedback to improve content quality
    - Use analytics to identify best-performing content formats and topics

Note: Exclude emojis, icons, or special characters from the script content and dont put [PAUSE] in the script.

5. Language:
    - The language of the script should match the language of the user input.
    - The language of the title should match the language of the user input.
    - The language of the hashtags should match the language of the user input.
`;
  }

  private parseContent(content: string, formatSpec: any): Content {
    let title = "";
    let script = "";
    let hashtags: string[] = [];
    let currentSection: "title" | "script" | "hashtags" | null = null;

    // Parse response line by line
    const lines = content.split("\n");
    for (const line of lines) {
      const trimmedLine = line.trim();
      if (!trimmedLine) continue;

      if (trimmedLine.startsWith("TITLE:")) {
        currentSection = "title";
        title = trimmedLine.replace("TITLE:", "").trim();
      } else if (trimmedLine.startsWith("SCRIPT:")) {
        currentSection = "script";
        script = trimmedLine.replace("SCRIPT:", "").trim();
      } else if (trimmedLine.startsWith("HASHTAGS:")) {
        currentSection = "hashtags";
        const hashtagsStr = trimmedLine.replace("HASHTAGS:", "").trim();
        hashtags = hashtagsStr.split(",").map((tag) => tag.trim());
      } else if (currentSection === "script") {
        script += "\n" + trimmedLine;
      }
    }

    // Validate content
    if (!title || !script || hashtags.length === 0) {
      console.error("Parsed Content:", { title, script, hashtags });
      throw new Error("Some content sections are missing");
    }

    return {
      title,
      script,
      hashtags,
      imagePrompts: [],
      format: {
        type: formatSpec.type,
      },
      formatDetails: {
        duration: formatSpec.duration,
        width: 0, // These will be set by the video generator
        height: 0,
        aspectRatio: formatSpec.type === "shorts" ? "9:16" : "16:9",
      },
      imageUrls: [],
    };
  }

  /**
   * Extract content from a URL
   * @param url The URL to extract content from
   * @returns Promise<ExtractedContent>
   */
  public async extractContentFromUrl(url: string): Promise<ExtractedContent> {
    try {
      // Fetch the webpage content with custom headers
      const response = await axios.get(url, { headers: this.headers });

      // Validate that we have HTML content
      if (!response.data || typeof response.data !== "string") {
        console.error("Invalid response data from URL:", url);
        return {
          title: "Content Extraction Failed",
          content: `Could not extract content from ${url}. The response was not valid HTML.`,
          images: [],
        };
      }

      const html = response.data;

      // Safely load HTML with cheerio
      let $;
      try {
        // Check if cheerio.load is defined
        if (typeof cheerio.load !== "function") {
          throw new Error("cheerio.load is not a function");
        }
        $ = cheerio.load(html);
      } catch (cheerioError) {
        console.error("Error parsing HTML with cheerio:", cheerioError);
        return {
          title: "Content Parsing Failed",
          content: `Could not parse content from ${url}. The HTML could not be processed.`,
          images: [],
        };
      }

      // Extract title
      let title =
        $('meta[property="og:title"]').attr("content") ||
        $('meta[name="twitter:title"]').attr("content") ||
        $("title").text() ||
        "";

      // Clean up title
      title = title.trim();

      // If no title found, use URL as fallback
      if (!title) {
        title = `Content from ${url}`;
      }

      // Extract main content
      let content = "";

      // Try to find the main content container
      const contentSelectors = [
        "article",
        '[role="main"]',
        ".post-content",
        ".entry-content",
        ".content",
        "main",
        "#main-content",
        "article.content-detail",
        "article.fck_detail",
        "div.fck_detail",
        "article.article-detail",
        "div.article-body",
        "div.article-content",
        'div[itemprop="articleBody"]',
        "div.detail-content",
        ".article__body",
        ".article__content",
        ".post-content",
        ".entry-content",
        "article.post",
        "main article",
        '[role="main"] article',
        ".main-content article",
        ".content article",
        ".articleDetail",
        ".content-detail",
        ".box-news",
        ".mw-content-container",
      ];

      for (const selector of contentSelectors) {
        const element = $(selector);
        if (element.length > 0) {
          content = element.text();
          break;
        }
      }

      // If no content found, try paragraphs
      if (!content) {
        content = $("p")
          .map((_, el) => $(el).text())
          .get()
          .join("\n\n");
      }

      // If still no content, extract body text as fallback
      if (!content) {
        content = $("body").text();
      }

      // Clean up content
      content = this.cleanContent(content);

      // Ensure we have some content
      if (!content) {
        content = `Could not extract meaningful content from ${url}. Please try a different URL or input your content manually.`;
      }
      console.log(
        content,
        "--------------------- content --------------------- \n ------------------- url --------------------- \n",
        url
      );

      // Extract images
      const images: string[] = [];

      // Try og:image first
      const ogImage = $('meta[property="og:image"]').attr("content");
      if (ogImage) images.push(ogImage);

      // Get other images
      $("img").each((_, el) => {
        const src = $(el).attr("src");
        const alt = $(el).attr("alt");

        // Only include images that are likely to be content-related
        if (
          src &&
          !src.includes("logo") &&
          !src.includes("icon") &&
          !src.includes("avatar") &&
          (alt || src.includes("content") || src.includes("post"))
        ) {
          try {
            // Convert relative URLs to absolute
            const absoluteUrl = new URL(src, url).href;
            images.push(absoluteUrl);
          } catch (urlError) {
            console.warn(`Could not process image URL: ${src}`, urlError);
            // Try to add the src directly if URL parsing fails
            if (src.startsWith("http")) {
              images.push(src);
            }
          }
        }
      });

      return {
        title,
        content,
        images: [...new Set(images)], // Remove duplicates
      };
    } catch (error) {
      console.error("Error extracting content from URL:", error);
      // Return a fallback object instead of throwing an error
      return {
        title: "Content Extraction Failed",
        content: `Could not extract content from ${url}. Error: ${error.message}`,
        images: [],
      };
    }
  }

  /**
   * Clean extracted content
   * @param content Raw content string
   * @returns Cleaned content string
   */
  private cleanContent(content: string): string {
    return content
      .replace(/\s+/g, " ") // Replace multiple spaces with single space
      .replace(/\n\s*\n/g, "\n\n") // Replace multiple newlines with double newline
      .replace(/\t/g, "") // Remove tabs
      .replace(/\r/g, "") // Remove carriage returns
      .trim() // Remove leading/trailing whitespace
      .split("\n") // Split into lines
      .filter((line) => {
        // Remove common noise
        const noise = [
          "cookie",
          "privacy policy",
          "terms of service",
          "subscribe",
          "newsletter",
          "advertisement",
          "loading",
          "share this",
          "follow us",
        ];
        return (
          line.trim() && !noise.some((n) => line.toLowerCase().includes(n))
        );
      })
      .join("\n"); // Join back into single string
  }

  /**
   * Download image from URL
   * @param imageUrl URL of the image to download
   * @param outputPath Path to save the image
   * @returns Promise<string> Path to downloaded image
   */
  private async downloadImage(
    imageUrl: string,
    outputPath: string
  ): Promise<string> {
    try {
      const response = await axios({
        url: imageUrl,
        method: "GET",
        responseType: "stream",
        headers: this.headers,
      });

      const writer = fs.createWriteStream(outputPath);
      response.data.pipe(writer);

      return new Promise((resolve, reject) => {
        writer.on("finish", () => resolve(outputPath));
        writer.on("error", reject);
      });
    } catch (error) {
      console.error("Error downloading image:", error);
      throw new Error(`Failed to download image: ${error.message}`);
    }
  }

  /**
   * Process URL content for video generation
   * @param url URL to process
   * @param outputDir Directory to save downloaded images
   * @returns Promise<{title: string, script: string, images: string[]}>
   */
  public async processUrlContent(
    url: string,
    outputDir: string
  ): Promise<{ title: string; script: string; images: string[] }> {
    try {
      // Extract content from URL
      const extracted = await this.extractContentFromUrl(url);

      // Create output directory if it doesn't exist
      fs.mkdirSync(outputDir, { recursive: true });

      // Download images
      const downloadedImages: string[] = [];
      if (extracted.images && extracted.images.length > 0) {
        for (let i = 0; i < extracted.images.length; i++) {
          try {
            const imageUrl = extracted.images[i];
            const ext = imageUrl.split(".").pop()?.split("?")[0] || "jpg";
            const imagePath = path.join(outputDir, `image_${i}.${ext}`);
            await this.downloadImage(imageUrl, imagePath);
            downloadedImages.push(imagePath);
          } catch (error) {
            console.warn(`Failed to download image ${i}:`, error);
          }
        }
      }

      return {
        title: extracted.title,
        script: extracted.content,
        images: downloadedImages,
      };
    } catch (error) {
      console.error("Error processing URL content:", error);
      throw error;
    }
  }
}

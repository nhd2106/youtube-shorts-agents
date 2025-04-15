"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ContentGenerator = void 0;
const openai_1 = require("openai");
const axios_1 = __importDefault(require("axios"));
const cheerio = __importStar(require("cheerio"));
const url_1 = require("url");
const path_1 = __importDefault(require("path"));
const fs_1 = __importDefault(require("fs"));
class ContentGenerator {
    constructor() {
        this.client = null;
        this.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "no-cache",
            Pragma: "no-cache",
        };
    }
    initClient(apiKeys) {
        if (!apiKeys.openai) {
            throw new Error("OpenAI API key is required");
        }
        this.client = new openai_1.OpenAI({ apiKey: apiKeys.openai });
    }
    async generateContent(idea, videoFormat = "shorts", apiKeys = {}) {
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
            this.initClient(apiKeys);
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
                throw new Error(`Invalid video format. Choose from: ${Object.keys(formatSpecs).join(", ")}`);
            }
            const formatSpec = formatSpecs[videoFormat];
            console.log(formatSpec, videoFormat);
            const response = await this.client.chat.completions.create({
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
            const content = this.parseContent(response.choices[0].message.content || "", formatSpec);
            return content;
        }
        catch (error) {
            console.error("Error generating content:", error);
            throw error;
        }
    }
    getSystemPrompt(formatSpec) {
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
    parseContent(content, formatSpec) {
        let title = "";
        let script = "";
        let hashtags = [];
        let currentSection = null;
        const lines = content.split("\n");
        for (const line of lines) {
            const trimmedLine = line.trim();
            if (!trimmedLine)
                continue;
            if (trimmedLine.startsWith("TITLE:")) {
                currentSection = "title";
                title = trimmedLine.replace("TITLE:", "").trim();
            }
            else if (trimmedLine.startsWith("SCRIPT:")) {
                currentSection = "script";
                script = trimmedLine.replace("SCRIPT:", "").trim();
            }
            else if (trimmedLine.startsWith("HASHTAGS:")) {
                currentSection = "hashtags";
                const hashtagsStr = trimmedLine.replace("HASHTAGS:", "").trim();
                hashtags = hashtagsStr.split(",").map((tag) => tag.trim());
            }
            else if (currentSection === "script") {
                script += "\n" + trimmedLine;
            }
        }
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
                width: 0,
                height: 0,
                aspectRatio: formatSpec.type === "shorts" ? "9:16" : "16:9",
            },
            imageUrls: [],
        };
    }
    async extractContentFromUrl(url) {
        try {
            const response = await axios_1.default.get(url, { headers: this.headers });
            if (!response.data || typeof response.data !== "string") {
                console.error("Invalid response data from URL:", url);
                return {
                    title: "Content Extraction Failed",
                    content: `Could not extract content from ${url}. The response was not valid HTML.`,
                    images: [],
                };
            }
            const html = response.data;
            let $;
            try {
                if (typeof cheerio.load !== "function") {
                    throw new Error("cheerio.load is not a function");
                }
                $ = cheerio.load(html);
            }
            catch (cheerioError) {
                console.error("Error parsing HTML with cheerio:", cheerioError);
                return {
                    title: "Content Parsing Failed",
                    content: `Could not parse content from ${url}. The HTML could not be processed.`,
                    images: [],
                };
            }
            let title = $('meta[property="og:title"]').attr("content") ||
                $('meta[name="twitter:title"]').attr("content") ||
                $("title").text() ||
                "";
            title = title.trim();
            if (!title) {
                title = `Content from ${url}`;
            }
            let content = "";
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
            if (!content) {
                content = $("p")
                    .map((_, el) => $(el).text())
                    .get()
                    .join("\n\n");
            }
            if (!content) {
                content = $("body").text();
            }
            content = this.cleanContent(content);
            if (!content) {
                content = `Could not extract meaningful content from ${url}. Please try a different URL or input your content manually.`;
            }
            console.log(content, "--------------------- content --------------------- \n ------------------- url --------------------- \n", url);
            const images = [];
            const ogImage = $('meta[property="og:image"]').attr("content");
            if (ogImage)
                images.push(ogImage);
            $("img").each((_, el) => {
                const src = $(el).attr("src");
                const alt = $(el).attr("alt");
                if (src &&
                    !src.includes("logo") &&
                    !src.includes("icon") &&
                    !src.includes("avatar") &&
                    (alt || src.includes("content") || src.includes("post"))) {
                    try {
                        const absoluteUrl = new url_1.URL(src, url).href;
                        images.push(absoluteUrl);
                    }
                    catch (urlError) {
                        console.warn(`Could not process image URL: ${src}`, urlError);
                        if (src.startsWith("http")) {
                            images.push(src);
                        }
                    }
                }
            });
            return {
                title,
                content,
                images: [...new Set(images)],
            };
        }
        catch (error) {
            console.error("Error extracting content from URL:", error);
            return {
                title: "Content Extraction Failed",
                content: `Could not extract content from ${url}. Error: ${error.message}`,
                images: [],
            };
        }
    }
    cleanContent(content) {
        return content
            .replace(/\s+/g, " ")
            .replace(/\n\s*\n/g, "\n\n")
            .replace(/\t/g, "")
            .replace(/\r/g, "")
            .trim()
            .split("\n")
            .filter((line) => {
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
            return (line.trim() && !noise.some((n) => line.toLowerCase().includes(n)));
        })
            .join("\n");
    }
    async downloadImage(imageUrl, outputPath) {
        try {
            const response = await (0, axios_1.default)({
                url: imageUrl,
                method: "GET",
                responseType: "stream",
                headers: this.headers,
            });
            const writer = fs_1.default.createWriteStream(outputPath);
            response.data.pipe(writer);
            return new Promise((resolve, reject) => {
                writer.on("finish", () => resolve(outputPath));
                writer.on("error", reject);
            });
        }
        catch (error) {
            console.error("Error downloading image:", error);
            throw new Error(`Failed to download image: ${error.message}`);
        }
    }
    async processUrlContent(url, outputDir) {
        try {
            const extracted = await this.extractContentFromUrl(url);
            fs_1.default.mkdirSync(outputDir, { recursive: true });
            const downloadedImages = [];
            if (extracted.images && extracted.images.length > 0) {
                for (let i = 0; i < extracted.images.length; i++) {
                    try {
                        const imageUrl = extracted.images[i];
                        const ext = imageUrl.split(".").pop()?.split("?")[0] || "jpg";
                        const imagePath = path_1.default.join(outputDir, `image_${i}.${ext}`);
                        await this.downloadImage(imageUrl, imagePath);
                        downloadedImages.push(imagePath);
                    }
                    catch (error) {
                        console.warn(`Failed to download image ${i}:`, error);
                    }
                }
            }
            return {
                title: extracted.title,
                script: extracted.content,
                images: downloadedImages,
            };
        }
        catch (error) {
            console.error("Error processing URL content:", error);
            throw error;
        }
    }
}
exports.ContentGenerator = ContentGenerator;
//# sourceMappingURL=ContentGenerator.js.map
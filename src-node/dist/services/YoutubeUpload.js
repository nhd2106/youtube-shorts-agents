"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.YoutubeUpload = void 0;
const googleapis_1 = require("googleapis");
const fs_1 = __importDefault(require("fs"));
class YoutubeUpload {
    constructor() {
        this.oauth2Client = new googleapis_1.google.auth.OAuth2(process.env.GOOGLE_CLIENT_ID, process.env.GOOGLE_CLIENT_SECRET, process.env.GOOGLE_REDIRECT_URI);
    }
    async uploadVideo(videoPath, title, description, tags, privacyStatus = "private") {
        try {
            this.oauth2Client.setCredentials({
                refresh_token: process.env.GOOGLE_REFRESH_TOKEN,
            });
            const youtube = googleapis_1.google.youtube({
                version: "v3",
                auth: this.oauth2Client,
            });
            const res = await youtube.videos.insert({
                part: ["snippet", "status"],
                requestBody: {
                    snippet: {
                        title,
                        description,
                        tags,
                        categoryId: "22",
                    },
                    status: {
                        privacyStatus,
                    },
                },
                media: {
                    body: fs_1.default.createReadStream(videoPath),
                },
            });
            return {
                videoId: res.data.id,
                url: `https://youtube.com/watch?v=${res.data.id}`,
            };
        }
        catch (error) {
            console.error("Error uploading video to YouTube:", error);
            throw error;
        }
    }
    async updateThumbnail(videoId, thumbnailPath) {
        try {
            const youtube = googleapis_1.google.youtube({
                version: "v3",
                auth: this.oauth2Client,
            });
            await youtube.thumbnails.set({
                videoId,
                media: {
                    body: fs_1.default.createReadStream(thumbnailPath),
                },
            });
            return true;
        }
        catch (error) {
            console.error("Error updating thumbnail:", error);
            throw error;
        }
    }
}
exports.YoutubeUpload = YoutubeUpload;
//# sourceMappingURL=YoutubeUpload.js.map
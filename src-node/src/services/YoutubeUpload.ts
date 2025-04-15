import { google } from "googleapis";
import fs from "fs";

export class YoutubeUpload {
  private oauth2Client;

  constructor() {
    this.oauth2Client = new google.auth.OAuth2(
      process.env.GOOGLE_CLIENT_ID,
      process.env.GOOGLE_CLIENT_SECRET,
      process.env.GOOGLE_REDIRECT_URI
    );
  }

  public async uploadVideo(
    videoPath: string,
    title: string,
    description: string,
    tags: string[],
    privacyStatus: "private" | "unlisted" | "public" = "private"
  ) {
    try {
      // Set credentials
      this.oauth2Client.setCredentials({
        refresh_token: process.env.GOOGLE_REFRESH_TOKEN,
      });

      const youtube = google.youtube({
        version: "v3",
        auth: this.oauth2Client,
      });

      // Upload video metadata
      const res = await youtube.videos.insert({
        part: ["snippet", "status"],
        requestBody: {
          snippet: {
            title,
            description,
            tags,
            categoryId: "22", // People & Blogs category
          },
          status: {
            privacyStatus,
          },
        },
        media: {
          body: fs.createReadStream(videoPath),
        },
      });

      return {
        videoId: res.data.id,
        url: `https://youtube.com/watch?v=${res.data.id}`,
      };
    } catch (error) {
      console.error("Error uploading video to YouTube:", error);
      throw error;
    }
  }

  public async updateThumbnail(videoId: string, thumbnailPath: string) {
    try {
      const youtube = google.youtube({
        version: "v3",
        auth: this.oauth2Client,
      });

      await youtube.thumbnails.set({
        videoId,
        media: {
          body: fs.createReadStream(thumbnailPath),
        },
      });

      return true;
    } catch (error) {
      console.error("Error updating thumbnail:", error);
      throw error;
    }
  }
}

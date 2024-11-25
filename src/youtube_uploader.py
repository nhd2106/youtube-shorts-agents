import os
from typing import Dict, Any, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle

class YouTubeUploader:
    def __init__(self):
        self.scopes = [
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube'
        ]
        self.api_name = 'youtube'
        self.api_version = 'v3'
        self.client_secrets_file = 'client_secrets.json'
        self.credentials_pickle = 'youtube_credentials.pickle'
        self.credentials = None
        self._youtube = None

    def _load_credentials(self) -> None:
        """Load or refresh credentials for YouTube API"""
        if os.path.exists(self.credentials_pickle):
            with open(self.credentials_pickle, 'rb') as token:
                self.credentials = pickle.load(token)

        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, self.scopes)
                self.credentials = flow.run_local_server(port=0)

            with open(self.credentials_pickle, 'wb') as token:
                pickle.dump(self.credentials, token)

    def _get_youtube_service(self):
        """Get authenticated YouTube service"""
        if not self._youtube:
            self._load_credentials()
            self._youtube = build(
                self.api_name,
                self.api_version,
                credentials=self.credentials
            )
        return self._youtube

    async def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        is_shorts: bool = True,
        privacy_status: str = 'private'
    ) -> Dict[str, Any]:
        """
        Upload a video to YouTube
        
        Args:
            video_path: Path to the video file
            title: Video title
            description: Video description
            tags: List of video tags
            is_shorts: Whether to mark the video as YouTube Shorts
            privacy_status: Privacy status ('private', 'unlisted', or 'public')
            
        Returns:
            Dictionary containing upload details including video ID and URL
        """
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")

            youtube = self._get_youtube_service()

            # Prepare video metadata
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags,
                    'categoryId': '22'  # People & Blogs category
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': False
                }
            }

            # Add shorts metadata if applicable
            if is_shorts:
                body['snippet']['tags'].append('#Shorts')

            # Create MediaFileUpload object
            media = MediaFileUpload(
                video_path,
                mimetype='video/*',
                resumable=True
            )

            # Execute upload request
            upload_request = youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )

            # Upload the video
            response = upload_request.execute()

            # Prepare response data
            video_id = response['id']
            video_url = f'https://youtube.com/watch?v={video_id}'
            shorts_url = f'https://youtube.com/shorts/{video_id}' if is_shorts else None

            return {
                'video_id': video_id,
                'video_url': video_url,
                'shorts_url': shorts_url,
                'privacy_status': privacy_status,
                'title': title
            }

        except Exception as e:
            raise Exception(f"Failed to upload video: {str(e)}")

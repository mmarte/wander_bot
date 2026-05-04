import json
import mimetypes
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional

import requests

from .settings import (
    FACEBOOK_PAGE_ACCESS_TOKEN,
    INSTAGRAM_BUSINESS_ACCOUNT_ID,
    X_BEARER_TOKEN,
    YOUTUBE_ACCESS_TOKEN,
    TIKTOK_ACCESS_TOKEN,
    TIKTOK_OPEN_ID,
    THREADS_AUTH_TOKEN,
    THREADS_USER_ID,
)

GRAPH_API_VERSION = "v17.0"
THREADS_API_BASES = ["https://graph.threads.net", "https://graph.threads.com"]


class SocialPlatformClient(ABC):
    @abstractmethod
    def publish_short(self, content: Dict[str, str], media_path: Optional[str] = None) -> Dict[str, str]:
        raise NotImplementedError

    def _is_url(self, path: str) -> bool:
        return isinstance(path, str) and path.startswith(("http://", "https://"))

    def _guess_mime_type(self, path: str) -> str:
        mime_type, _ = mimetypes.guess_type(path)
        return mime_type or "application/octet-stream"


class InstagramPoster(SocialPlatformClient):
    def publish_short(self, content: Dict[str, str], media_path: Optional[str] = None) -> Dict[str, str]:
        if not FACEBOOK_PAGE_ACCESS_TOKEN or not INSTAGRAM_BUSINESS_ACCOUNT_ID:
            return {"status": "error", "message": "Instagram credentials are missing."}

        if not media_path:
            return {"status": "error", "message": "Instagram requires a publicly accessible video_url for reel uploads."}

        if not self._is_url(media_path):
            return {
                "status": "error",
                "message": "Instagram Graph API requires a video URL for reel publishing. Upload your media to cloud storage and provide the URL.",
            }

        try:
            create_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
            payload = {
                "video_url": media_path,
                "media_type": "REEL",
                "caption": content.get("caption", ""),
                "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
            }
            creation = requests.post(create_url, data=payload, timeout=60)
            creation.raise_for_status()
            creation_data = creation.json()
            creation_id = creation_data.get("id")
            if not creation_id:
                return {"status": "error", "message": "Instagram media creation failed.", "details": creation_data}

            publish_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
            publish_response = requests.post(
                publish_url,
                data={"creation_id": creation_id, "access_token": FACEBOOK_PAGE_ACCESS_TOKEN},
                timeout=60,
            )
            publish_response.raise_for_status()
            publish_data = publish_response.json()
            return {
                "status": "ok",
                "platform": "instagram",
                "creation_id": creation_id,
                "publish_response": publish_data,
            }
        except requests.RequestException as exc:
            return {"status": "error", "message": "Instagram API request failed.", "details": str(exc)}


class FacebookPoster(SocialPlatformClient):
    def publish_short(self, content: Dict[str, str], media_path: Optional[str] = None) -> Dict[str, str]:
        if not FACEBOOK_PAGE_ACCESS_TOKEN:
            return {"status": "error", "message": "Facebook Page access token is missing."}

        if not media_path:
            return {"status": "error", "message": "Facebook requires a video media_path to upload."}

        upload_url = f"https://graph-video.facebook.com/{GRAPH_API_VERSION}/me/videos"
        data = {
            "description": content.get("caption", ""),
            "title": content.get("title", ""),
            "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
        }

        try:
            files = {}
            if self._is_url(media_path):
                data["file_url"] = media_path
                response = requests.post(upload_url, data=data, timeout=120)
            else:
                with open(media_path, "rb") as handle:
                    files["source"] = handle
                    response = requests.post(upload_url, data=data, files=files, timeout=120)
            response.raise_for_status()
            return {"status": "ok", "platform": "facebook", "response": response.json()}
        except requests.RequestException as exc:
            return {"status": "error", "message": "Facebook video upload failed.", "details": str(exc)}
        except FileNotFoundError:
            return {"status": "error", "message": f"Facebook media file not found: {media_path}"}


class TikTokPoster(SocialPlatformClient):
    def publish_short(self, content: Dict[str, str], media_path: Optional[str] = None) -> Dict[str, str]:
        if not TIKTOK_ACCESS_TOKEN or not TIKTOK_OPEN_ID:
            return {"status": "error", "message": "TikTok access token or open_id is missing."}

        if not media_path:
            return {"status": "error", "message": "TikTok requires a local video file path to upload."}

        try:
            upload_url = f"https://open-api.tiktok.com/video/upload/?open_id={TIKTOK_OPEN_ID}&access_token={TIKTOK_ACCESS_TOKEN}"
            with open(media_path, "rb") as handle:
                response = requests.post(upload_url, files={"video": handle}, timeout=180)
            response.raise_for_status()
            upload_data = response.json()
            video_id = upload_data.get("data", {}).get("video_id")
            if not video_id:
                return {"status": "error", "message": "TikTok video upload failed.", "details": upload_data}

            publish_url = f"https://open-api.tiktok.com/video/publish/?open_id={TIKTOK_OPEN_ID}&access_token={TIKTOK_ACCESS_TOKEN}"
            publish_response = requests.post(
                publish_url,
                data={"video_id": video_id, "text": content.get("caption", "")},
                timeout=60,
            )
            publish_response.raise_for_status()
            return {"status": "ok", "platform": "tiktok", "video_id": video_id, "response": publish_response.json()}
        except requests.RequestException as exc:
            return {"status": "error", "message": "TikTok API request failed.", "details": str(exc)}
        except FileNotFoundError:
            return {"status": "error", "message": f"TikTok media file not found: {media_path}"}


class YouTubePoster(SocialPlatformClient):
    def publish_short(self, content: Dict[str, str], media_path: Optional[str] = None) -> Dict[str, str]:
        if not YOUTUBE_ACCESS_TOKEN:
            return {"status": "error", "message": "YouTube OAuth access token is missing."}

        if not media_path:
            return {"status": "error", "message": "YouTube requires a local video file path to upload."}

        try:
            init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
            headers = {
                "Authorization": f"Bearer {YOUTUBE_ACCESS_TOKEN}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/*",
            }
            snippet = {
                "title": content.get("title", "WanderWithZen Short"),
                "description": content.get("caption", ""),
                "tags": self._build_tags(content.get("hashtags", "")),
                "categoryId": "19",
            }
            payload = {"snippet": snippet, "status": {"privacyStatus": "public"}}
            init_response = requests.post(init_url, headers=headers, json=payload, timeout=30)
            init_response.raise_for_status()
            upload_url = init_response.headers.get("Location")
            if not upload_url:
                return {"status": "error", "message": "YouTube resumable upload URL was not returned."}

            with open(media_path, "rb") as handle:
                upload_response = requests.put(
                    upload_url,
                    data=handle,
                    headers={
                        "Authorization": f"Bearer {YOUTUBE_ACCESS_TOKEN}",
                        "Content-Type": "video/*",
                    },
                    timeout=300,
                )
            upload_response.raise_for_status()
            return {"status": "ok", "platform": "youtube", "response": upload_response.json()}
        except requests.RequestException as exc:
            return {"status": "error", "message": "YouTube API request failed.", "details": str(exc)}
        except FileNotFoundError:
            return {"status": "error", "message": f"YouTube media file not found: {media_path}"}

    def _build_tags(self, hashtags: str) -> list[str]:
        return [tag.strip().lstrip("#") for tag in hashtags.split() if tag.strip()]


class XPoster(SocialPlatformClient):
    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {X_BEARER_TOKEN}"}

    def publish_short(self, content: Dict[str, str], media_path: Optional[str] = None) -> Dict[str, str]:
        if not X_BEARER_TOKEN:
            return {"status": "error", "message": "X bearer token is missing."}

        if not media_path:
            return {"status": "error", "message": "X requires a local media file path to upload."}

        try:
            media_id = self._upload_media(media_path)
            if not media_id:
                return {"status": "error", "message": "X media upload failed."}

            create_url = "https://api.twitter.com/2/tweets"
            payload = {"text": content.get("caption", ""), "media": {"media_ids": [media_id]}}
            response = requests.post(create_url, headers={**self._headers(), "Content-Type": "application/json"}, json=payload, timeout=60)
            response.raise_for_status()
            return {"status": "ok", "platform": "x", "response": response.json()}
        except requests.RequestException as exc:
            return {"status": "error", "message": "X API request failed.", "details": str(exc)}
        except FileNotFoundError:
            return {"status": "error", "message": f"X media file not found: {media_path}"}

    def _upload_media(self, media_path: str) -> Optional[str]:
        upload_url = "https://upload.twitter.com/1.1/media/upload.json"
        file_size = Path(media_path).stat().st_size
        mime_type = self._guess_mime_type(media_path)
        init_response = requests.post(
            upload_url,
            headers=self._headers(),
            data={
                "command": "INIT",
                "total_bytes": str(file_size),
                "media_type": mime_type,
                "media_category": "tweet_video",
            },
            timeout=60,
        )
        init_response.raise_for_status()
        init_data = init_response.json()
        media_id = init_data.get("media_id_string")
        if not media_id:
            return None

        with open(media_path, "rb") as handle:
            append_response = requests.post(
                upload_url,
                headers=self._headers(),
                data={"command": "APPEND", "media_id": media_id, "segment_index": "0"},
                files={"media": handle},
                timeout=120,
            )
        append_response.raise_for_status()

        finalize_response = requests.post(
            upload_url,
            headers=self._headers(),
            data={"command": "FINALIZE", "media_id": media_id},
            timeout=60,
        )
        finalize_response.raise_for_status()
        finalize_data = finalize_response.json()

        processing_info = finalize_data.get("processing_info")
        if processing_info:
            return self._poll_media_status(media_id, processing_info)

        return media_id

    def _poll_media_status(self, media_id: str, processing_info: Dict[str, str]) -> Optional[str]:
        upload_url = "https://upload.twitter.com/1.1/media/upload.json"
        status = processing_info
        while status and status.get("state") not in ("succeeded", "failed"):
            time.sleep(int(status.get("check_after_secs", 5)))
            status_response = requests.get(
                upload_url,
                headers=self._headers(),
                params={"command": "STATUS", "media_id": media_id},
                timeout=60,
            )
            status_response.raise_for_status()
            status = status_response.json().get("processing_info")
        return media_id if status and status.get("state") == "succeeded" else None


class ThreadsPoster(SocialPlatformClient):
    def publish_short(self, content: Dict[str, str], media_path: Optional[str] = None) -> Dict[str, str]:
        if not THREADS_AUTH_TOKEN or not THREADS_USER_ID:
            return {"status": "error", "message": "Threads auth token or user ID is missing."}

        data = {"message": content.get("caption", "")}
        files = None
        if media_path:
            if self._is_url(media_path):
                data["media_url"] = media_path
            else:
                try:
                    files = {"file": open(media_path, "rb")}
                except FileNotFoundError:
                    return {"status": "error", "message": f"Threads media file not found: {media_path}"}

        headers = {"Authorization": f"Bearer {THREADS_AUTH_TOKEN}"}
        last_error = None
        for base in THREADS_API_BASES:
            publish_url = f"{base}/{THREADS_USER_ID}/posts"
            try:
                response = requests.post(publish_url, headers=headers, data=data, files=files, timeout=60)
                response.raise_for_status()
                return {"status": "ok", "platform": "threads", "response": response.json()}
            except requests.RequestException as exc:
                last_error = str(exc)
                continue
            finally:
                if files:
                    files["file"].close()

        return {"status": "error", "message": "Threads publish endpoint failed.", "details": last_error}

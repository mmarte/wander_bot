import json
import mimetypes
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional

import requests

from .settings import (
    FACEBOOK_PAGE_ID,
    FACEBOOK_PAGE_ACCESS_TOKEN,
    INSTAGRAM_BUSINESS_ACCOUNT_ID,
    X_BEARER_TOKEN,
    YOUTUBE_ACCESS_TOKEN,
    TIKTOK_ACCESS_TOKEN,
    TIKTOK_OPEN_ID,
    THREADS_AUTH_TOKEN,
    THREADS_USER_ID,
    X_USER_TOKEN,
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_REFRESH_TOKEN,
)

GRAPH_API_VERSION = "v25.0"


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

        if not FACEBOOK_PAGE_ID:
            return {"status": "error", "message": "Facebook Page ID is missing."}

        if not media_path:
            upload_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{FACEBOOK_PAGE_ID}/feed"
            try:
                response = requests.post(
                    upload_url,
                    data={
                        "message": content.get("caption", ""),
                        "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
                    },
                    timeout=60,
                )
                data = response.json()
                if response.status_code >= 400 or data.get("error"):
                    error = data.get("error", {})
                    if error.get("code") == 200:
                        return {
                            "status": "error",
                            "message": "Facebook Page token lacks pages_manage_posts and/or pages_read_engagement for this Page.",
                            "details": data,
                        }
                    if error.get("code") == 100:
                        return {
                            "status": "error",
                            "message": "Facebook Page ID does not match the Page token, or that ID is not a valid Page for this call.",
                            "details": data,
                        }
                    return {"status": "error", "message": "Facebook post failed.", "details": data}
                return {"status": "ok", "platform": "facebook", "response": data}
            except requests.RequestException as exc:
                return {"status": "error", "message": "Facebook post failed.", "details": str(exc)}

        upload_url = f"https://graph-video.facebook.com/{GRAPH_API_VERSION}/{FACEBOOK_PAGE_ID}/videos"
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

        # TikTok Content Posting API v2 (the old open-api.tiktok.com
        # video/upload endpoint is deprecated). The TikTok app must be
        # approved for Content Posting API, otherwise init returns 403.
        try:
            import os
            size = os.path.getsize(media_path)
            headers = {
                "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
                "Content-Type": "application/json; charset=UTF-8",
            }
            init = requests.post(
                "https://open.tiktokapis.com/v2/post/publish/video/init/",
                headers=headers,
                json={
                    "post_info": {
                        "title": content.get("caption", "")[:150],
                        "privacy_level": "PUBLIC_TO_EVERYONE",
                        "disable_comment": False,
                        "disable_duet": False,
                        "disable_stitch": False,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": size,
                        "chunk_size": size,
                        "total_chunk_count": 1,
                    },
                },
                timeout=60,
            )
            init_data = init.json()
            if init.status_code >= 400 or init_data.get("error"):
                return {"status": "error", "message": "TikTok video init failed.", "details": init_data}
            data = init_data.get("data", {})
            upload_url = data.get("upload_url")
            publish_id = data.get("publish_id")
            if not upload_url:
                return {"status": "error", "message": "TikTok video init failed.", "details": init_data}
            with open(media_path, "rb") as handle:
                up = requests.put(
                    upload_url,
                    data=handle,
                    headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{size - 1}/{size}"},
                    timeout=300,
                )
            if up.status_code >= 400:
                return {"status": "error", "message": "TikTok video upload failed.", "details": up.text[:500]}
            return {"status": "ok", "platform": "tiktok", "publish_id": publish_id, "response": init_data}
        except requests.RequestException as exc:
            return {"status": "error", "message": "TikTok API request failed.", "details": str(exc)}
        except FileNotFoundError:
            return {"status": "error", "message": f"TikTok media file not found: {media_path}"}


class YouTubePoster(SocialPlatformClient):
    def _access_token(self) -> str:
        # Prefer refresh-token flow (long-lived, like rock_bot make_reel.py).
        # A static YOUTUBE_ACCESS_TOKEN expires in about an hour.
        if YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN:
            try:
                r = requests.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": YOUTUBE_CLIENT_ID,
                        "client_secret": YOUTUBE_CLIENT_SECRET,
                        "refresh_token": YOUTUBE_REFRESH_TOKEN,
                        "grant_type": "refresh_token",
                    },
                    timeout=30,
                )
                r.raise_for_status()
                tok = r.json().get("access_token")
                if tok:
                    return tok
            except Exception:
                pass
        return YOUTUBE_ACCESS_TOKEN or ""

    def publish_short(self, content: Dict[str, str], media_path: Optional[str] = None) -> Dict[str, str]:
        access_token = self._access_token()
        if not access_token:
            return {"status": "error", "message": "YouTube OAuth access token is missing. Set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN, or a fresh YOUTUBE_ACCESS_TOKEN."}

        if not media_path:
            return {"status": "error", "message": "YouTube requires a local video file path to upload."}

        try:
            init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
            headers = {
                "Authorization": f"Bearer {access_token}",
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
                        "Authorization": f"Bearer {access_token}",
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
        # Posting requires a user token (OAuth 2.0 user or OAuth 1.0a user),
        # not an app-only bearer token. X_USER_TOKEN is preferred.
        tok = X_USER_TOKEN or X_BEARER_TOKEN
        return {"Authorization": f"Bearer {tok}"}

    def publish_short(self, content: Dict[str, str], media_path: Optional[str] = None) -> Dict[str, str]:
        if not (X_USER_TOKEN or X_BEARER_TOKEN):
            return {"status": "error", "message": "X user token is missing. Set X_USER_TOKEN (OAuth user token); an app-only bearer token cannot post."}

        try:
            if not media_path:
                # Text-only tweet, no media upload needed.
                response = requests.post(
                    "https://api.twitter.com/2/tweets",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={"text": content.get("caption", "")[:280]},
                    timeout=60,
                )
                response.raise_for_status()
                return {"status": "ok", "platform": "x", "response": response.json()}
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

        # Threads API: create a container, then publish it. There is no
        # /{user-id}/posts file-upload endpoint. A local video file cannot
        # be posted directly — it needs a publicly accessible video_url.
        # For reels, use publish_reel.py for Facebook/Instagram and post
        # the text version here, or pass a public video URL as media_path.
        if media_path and not self._is_url(media_path):
            return {
                "status": "error",
                "message": "Threads requires a publicly accessible video/image URL for media. Pass a URL as media_path, or publish text only.",
            }

        params = {
            "text": content.get("caption", "")[:500],
            "access_token": THREADS_AUTH_TOKEN,
        }
        if media_path:
            if media_path.lower().endswith((".mp4", ".mov")):
                params["media_type"] = "VIDEO"
                params["video_url"] = media_path
            else:
                params["media_type"] = "IMAGE"
                params["image_url"] = media_path
        else:
            params["media_type"] = "TEXT"

        try:
            create = requests.post(
                f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads",
                data=params,
                timeout=60,
            )
            create_data = create.json()
            if create.status_code >= 400 or create_data.get("error"):
                return {"status": "error", "message": "Threads container creation failed.", "details": create_data}
            creation_id = create_data.get("id") or create_data.get("creation_id")
            if not creation_id:
                return {"status": "error", "message": "Threads container creation failed.", "details": create_data}

            publish = requests.post(
                f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish",
                data={"creation_id": creation_id, "access_token": THREADS_AUTH_TOKEN},
                timeout=60,
            )
            publish_data = publish.json()
            if publish.status_code >= 400 or publish_data.get("error"):
                return {"status": "error", "message": "Threads publish failed.", "details": publish_data}
            return {"status": "ok", "platform": "threads", "response": publish_data}
        except requests.RequestException as exc:
            return {"status": "error", "message": "Threads API request failed.", "details": str(exc)}

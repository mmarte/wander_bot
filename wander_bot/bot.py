from typing import Dict, List, Optional

from .content_generator import SocialContentGenerator
from .platforms import (
    FacebookPoster,
    InstagramPoster,
    TikTokPoster,
    YouTubePoster,
    XPoster,
    ThreadsPoster,
    SocialPlatformClient,
)


PLATFORM_MAP = {
    "instagram": InstagramPoster,
    "facebook": FacebookPoster,
    "tiktok": TikTokPoster,
    "youtube": YouTubePoster,
    "x": XPoster,
    "threads": ThreadsPoster,
}


class WanderBot:
    def __init__(self, theme: str = "Wanderwithzen travel, nature, and mindful adventure"):
        self.generator = SocialContentGenerator(theme=theme)

    def generate(self, location: str, platform: str = "instagram", count: int = 1) -> List[Dict[str, str]]:
        return self.generator.generate_short_form(location, count=count, platform=platform)

    def publish(self, content: Dict[str, str], platform: str, media_path: Optional[str] = None) -> Dict[str, str]:
        poster = self._get_poster(platform)
        return poster.publish_short(content, media_path=media_path)

    def _get_poster(self, platform: str) -> SocialPlatformClient:
        platform = platform.lower()
        poster_class = PLATFORM_MAP.get(platform)
        if poster_class is None:
            raise ValueError(f"Platform '{platform}' is not supported.")
        return poster_class()

import os
from typing import List, Dict, Optional

try:
    import openai
except ImportError:  # pragma: no cover
    openai = None

from .settings import OPENAI_API_KEY


class SocialContentGenerator:
    """Generate travel/adventure content for short-form social media posts."""

    def __init__(self, theme: str = "travel and adventure", model: str = "gpt-4o-mini"):
        self.theme = theme
        self.model = model
        self.api_key = OPENAI_API_KEY
        if openai and self.api_key:
            openai.api_key = self.api_key

    def generate_short_form(self, location: str, count: int = 1, platform: str = "instagram") -> List[Dict[str, str]]:
        """Generate one or more short-form content ideas."""
        results = []
        for index in range(count):
            prompt = self._build_prompt(location, platform, index + 1)
            completion = self._complete_prompt(prompt)
            results.append(completion)
        return results

    def _build_prompt(self, location: str, platform: str, number: int) -> str:
        return (
            f"You are a travel content creator specializing in reels, stories, and shorts. "
            f"Produce a single short-form post idea for {platform} about travel and adventure at {location}. "
            "Include: title, caption, hashtags, shot list, mood, and a call to action. "
            "Use concise, engaging language and keep it optimized for short-form video. "
            "Present the result as JSON with keys: title, caption, hashtags, video_idea, cta. "
            f"Idea number {number}."
        )

    def _complete_prompt(self, prompt: str) -> Dict[str, str]:
        if openai and self.api_key:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "system", "content": "You are a creative social media writer."},
                          {"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.8,
            )
            text = response.choices[0].message.content.strip()
            return self._parse_response(text)

        return self._fallback_prompt(prompt)

    def _parse_response(self, text: str) -> Dict[str, str]:
        # Minimal JSON extraction fallback. If the response is not valid JSON, return raw text.
        try:
            import json

            payload = json.loads(text)
            return {
                "title": payload.get("title", "Travel Short"),
                "caption": payload.get("caption", "Discover the next adventure!"),
                "hashtags": payload.get("hashtags", "#travel #adventure"),
                "video_idea": payload.get("video_idea", "Showcase a sunrise hike and local flavors."),
                "cta": payload.get("cta", "Follow for more travel stories."),
            }
        except Exception:
            return {
                "title": "Travel Short",
                "caption": text,
                "hashtags": "#travel #adventure #wanderwithzen",
                "video_idea": text,
                "cta": "Follow for more travel and adventure content.",
            }

    def _fallback_prompt(self, prompt: str) -> Dict[str, str]:
        return {
            "title": "Escape the noise, find your path",
            "caption": f"Explore {prompt.split(' at ')[-1].split('.')[0]} with me — nature, hidden trails, and world-class views. #travel #adventure #wanderwithzen",
            "hashtags": "#travel #adventure #nature #wanderlust",
            "video_idea": "Start with a fast-paced arrival shot, then show a scenic hike, local food, and a quiet sunset moment.",
            "cta": "Save this reel and follow for more adventure escapes.",
        }

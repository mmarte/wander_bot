import os
import random
from typing import List, Dict, Optional

try:
    import openai
except ImportError:  # pragma: no cover
    openai = None

from .settings import OPENAI_API_KEY
from .settings import GROQ_API_KEY

try:
    from groq import Groq
except ImportError:  # pragma: no cover
    Groq = None


def _salvage_fields(text: str) -> Dict[str, str]:
    """Best-effort extraction of string fields from JSON that will not parse
    (e.g. the model was cut off mid-object). The caption field comes before
    the shot list, so it usually survives truncation intact."""
    import json
    import re

    found: Dict[str, str] = {}
    for key in ("title", "caption", "hashtags", "cta"):
        match = re.search(r'"' + key + r'"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if match:
            try:
                found[key] = json.loads(f'"{match.group(1)}"')
            except Exception:
                found[key] = match.group(1)
    return found


def get_pexels_photo(query: str) -> str:
    """Return a Pexels photo URL matching the query (landscape), or "".
    Used to put a picture on Wanderwithzen text posts. Fail-soft: any
    problem returns "" and the post goes out text-only, as before."""
    import requests

    key = os.getenv("PEXELS_API_KEY")
    if not key or not query:
        return ""
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": key},
            params={"query": query, "per_page": 5, "orientation": "landscape"},
            timeout=15,
        )
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if not photos:
            return ""
        return random.choice(photos).get("src", {}).get("large", "") or ""
    except Exception as e:
        print(f"  Pexels photo error: {e}")
        return ""


class SocialContentGenerator:
    """Generate travel/adventure content for short-form social media posts."""

    def __init__(self, theme: str = "Wanderwithzen travel, nature, and mindful adventure", model: str = "gpt-4o-mini"):
        self.theme = theme
        self.model = model
        self.api_key = OPENAI_API_KEY
        self.client = openai.OpenAI(api_key=self.api_key) if openai and self.api_key else None
        self.groq_client = Groq(api_key=GROQ_API_KEY) if Groq and GROQ_API_KEY else None

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
            f"You are the content creator for Wanderwithzen, a travel, nature, and mindful adventure page. "
            f"Produce a single short-form post idea for {platform} about an inspiring journey or destination at {location}. "
            "Include: title, caption, hashtags, shot list, mood, and a call to action. "
            "Use concise, engaging language and keep it optimized for short-form video. "
            "Present the result as JSON with keys: title, caption, hashtags, video_idea, cta. "
            f"Idea number {number}."
        )

    def _complete_prompt(self, prompt: str) -> Dict[str, str]:
        if self.groq_client:
            response = self.groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "system", "content": "You are a creative social media writer."},
                          {"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.8,
            )
            text = response.choices[0].message.content.strip()
            return self._parse_response(text)

        if self.client:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": "You are a creative social media writer."},
                          {"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.8,
            )
            text = response.choices[0].message.content.strip()
            return self._parse_response(text)

        return self._fallback_prompt(prompt)

    def _parse_response(self, text: str) -> Dict[str, str]:
        # 2026-11-06: the model wraps its JSON in ```json fences (and
        # sometimes in prose), so plain json.loads() always failed and the
        # except branch posted the whole raw blob as the caption — that is
        # what the Nov 6 test post showed (post text started with ```json).
        # Strip fences first, then fall back to brace extraction, so the
        # parsed caption is what gets posted.
        import json

        cleaned = text.strip()
        lines = cleaned.split("\n")
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
        payload = None
        try:
            payload = json.loads(cleaned)
        except Exception:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end > start:
                try:
                    payload = json.loads(cleaned[start:end + 1])
                except Exception:
                    payload = None
        if isinstance(payload, dict):
            caption = str(payload.get("caption") or "Discover the next adventure!").strip()
            hashtags = str(payload.get("hashtags") or "#travel #adventure").strip()
            if hashtags and hashtags not in caption:
                caption = f"{caption}\n\n{hashtags}"
            return {
                "title": payload.get("title", "Travel Short"),
                "caption": caption,
                "hashtags": hashtags,
                "video_idea": payload.get("video_idea", "Showcase a sunrise hike and local flavors."),
                "cta": payload.get("cta", "Follow for more travel stories."),
            }
        salvaged = _salvage_fields(cleaned)
        if salvaged.get("caption"):
            caption = salvaged["caption"]
            hashtags = salvaged.get("hashtags", "")
            if hashtags and hashtags not in caption:
                caption = f"{caption}\n\n{hashtags}"
            return {
                "title": salvaged.get("title") or "Travel Short",
                "caption": caption,
                "hashtags": hashtags or "#travel #adventure",
                "video_idea": cleaned,
                "cta": salvaged.get("cta") or "Follow for more travel stories.",
            }
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

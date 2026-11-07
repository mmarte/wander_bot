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


# Real places people can actually travel to. The bot rotates one per day,
# so every text post is about a real, visitable destination — never an
# invented place. "match" is the distinctive token the guard looks for
# in the generated title/caption (accents ignored).
REAL_PLACES = [
    {"name": "Lake Atitlán", "country": "Guatemala", "match": "atitlán", "blurb": "a volcanic lake ringed by three volcanoes, reached by boat from Panajachel"},
    {"name": "Tikal", "country": "Guatemala", "match": "tikal", "blurb": "a Maya city rising out of the Petén jungle, reached on foot through the national park"},
    {"name": "Semuc Champey", "country": "Guatemala", "match": "semuc", "blurb": "a limestone bridge of turquoise pools over the Cahabón River, reached by a jungle trail"},
    {"name": "Antigua Guatemala", "country": "Guatemala", "match": "antigua", "blurb": "a colonial city under the Agua volcano, walked on cobbled streets"},
    {"name": "Machu Picchu", "country": "Peru", "match": "machu", "blurb": "an Inca citadel in the Andes, reached by train to Aguas Calientes and bus up the mountain"},
    {"name": "Torres del Paine", "country": "Chile", "match": "paine", "blurb": "granite towers over turquoise lakes in Patagonia, hiked on the W trek"},
    {"name": "Banff National Park", "country": "Canada", "match": "banff", "blurb": "turquoise lakes and peaks in the Canadian Rockies, driven on the Icefields Parkway"},
    {"name": "Plitvice Lakes", "country": "Croatia", "match": "plitvice", "blurb": "a chain of terraced turquoise lakes joined by boardwalks and waterfalls"},
    {"name": "Santorini", "country": "Greece", "match": "santorini", "blurb": "a volcanic island of white villages above a blue caldera, walked along the cliff path from Fira to Oia"},
    {"name": "Bali", "country": "Indonesia", "match": "bali", "blurb": "an island of rice terraces, temples and surf, explored by scooter from Ubud"},
    {"name": "Lofoten Islands", "country": "Norway", "match": "lofoten", "blurb": "Arctic peaks rising straight from the sea, driven on the E10 past fishing villages"},
    {"name": "Huacachina", "country": "Peru", "match": "huacachina", "blurb": "a desert oasis ringed by sand dunes, reached by dune buggy from Ica"},
    {"name": "Salar de Uyuni", "country": "Bolivia", "match": "uyuni", "blurb": "the world's largest salt flat, crossed by 4x4 under a sky that mirrors the ground"},
    {"name": "Cappadocia", "country": "Turkey", "match": "cappadocia", "blurb": "fairy chimneys and cave villages, seen from a balloon at sunrise over Göreme"},
    {"name": "Hallstatt", "country": "Austria", "match": "hallstatt", "blurb": "a lakeside village under the Dachstein mountains, walked along the shore from the ferry pier"},
    {"name": "Faroe Islands", "country": "Denmark", "match": "faroe", "blurb": "sea cliffs and grass-roofed villages in the North Atlantic, driven between tunnels and fjords"},
    {"name": "Milford Sound", "country": "New Zealand", "match": "milford", "blurb": "a fjord of waterfalls and sheer cliffs, cruised after the drive through Homer Tunnel"},
    {"name": "Jeju Island", "country": "South Korea", "match": "jeju", "blurb": "a volcanic island of lava tubes, waterfalls and Hallasan, hiked and driven on the coastal road"},
    {"name": "Bora Bora", "country": "French Polynesia", "match": "bora", "blurb": "a turquoise lagoon around Mount Otemanu, reached by boat from Vaitape"},
    {"name": "Chefchaouen", "country": "Morocco", "match": "chefchaouen", "blurb": "a blue-painted mountain town in the Rif, walked through its blue alleys"},
    {"name": "Zhangjiajie", "country": "China", "match": "zhangjiajie", "blurb": "sandstone pillars above the clouds, walked on the glass bridge and mountain trails"},
    {"name": "Amalfi Coast", "country": "Italy", "match": "amalfi", "blurb": "cliff villages above the Tyrrhenian Sea, driven or boated between Positano and Amalfi"},
    {"name": "Isle of Skye", "country": "Scotland", "match": "skye", "blurb": "sea cliffs, fairy pools and the Cuillin ridge, driven on the island's single-track roads"},
    {"name": "Wadi Rum", "country": "Jordan", "match": "wadi rum", "blurb": "a red desert of canyons and dunes, camped under the stars with Bedouin guides"},
]


def pick_place(offset: int = 0) -> Dict[str, str]:
    """One real, visitable place per UTC day (rotates through REAL_PLACES)."""
    from datetime import datetime, timezone

    day_index = int(datetime.now(timezone.utc).timestamp() // 86400)
    return REAL_PLACES[(day_index + offset) % len(REAL_PLACES)]


def _normalize(text: str) -> str:
    import unicodedata

    nfkd = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def ensure_place_in_post(idea: Dict[str, str], place: Dict[str, str]) -> Dict[str, str]:
    """Guard: the post must name its real place. If the generated title and
    caption never mention it, replace them with a safe template built from
    the place's own verified blurb, so a drifted post can never go out
    about a place that does not exist."""
    hay = _normalize(f"{idea.get('title', '')} {idea.get('caption', '')}")
    if _normalize(place["match"]) in hay:
        return idea
    idea["title"] = f"Discover {place['name']}"
    blurb = place["blurb"]
    blurb = blurb[0].upper() + blurb[1:] if blurb else blurb
    idea["caption"] = (
        f"Discover {place['name']}, {place['country']}. {blurb}. "
        "Slow down, look around, and let the place do the talking."
    )
    return idea


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

"""
make_reel.py
------------
Generates a 60-second Wanderwithzen travel Reel — 100% free:
  1. Groq  → writes Spanish script
  2. Kokoro → converts to Spanish voiceover (free, local, no API key)
  3. Pexels → fetches video clips
  4. MoviePy → assembles 9:16 vertical Reel

Output: reels/reel_YYYYMMDD.mp4  — download from GitHub Actions artifacts,
        upload to Facebook/Instagram manually (takes ~5 minutes)

Run manually:  python make_reel.py
Runs via cron: every day at 09:00 UTC (GitHub Actions)
"""

import os
import random
import requests
import tempfile
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

try:
    from find_video import get_video_for_topic
except Exception:
    get_video_for_topic = None

load_dotenv()

GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
PEXELS_KEY    = os.getenv("PEXELS_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

OUTPUT_DIR = Path("reels")
OUTPUT_DIR.mkdir(exist_ok=True)

# Reel topics — rotated by calendar day so daily runs get variety.
# 2026-11-06: rebalanced toward the @wanderwithzen style — aerial/drone
# shots of turquoise bays, tropical coasts and palm shores, travel-focused.
# Coastal/aerial topics lead the rotation; the rest keep variety.
# 2026-11-07: every reel topic is anchored on a REAL place, the same
# rule the text posts follow. The script must name the place and its
# country, and the caption carries #Place #Country tags (publish_reel.py
# reads the Place line out of the script file header). Places are real
# and matched to the theme; the Pexels search stays the generic theme
# query — footage of the exact place is not required.
# 2026-11-07, second change: each theme now has THREE places in three
# different countries, and pick_topic() chooses one at random per run,
# so the country varies instead of every reel about a theme naming the
# same place. Picking a country first and forcing a theme to fit would
# break the reel (desert theme, rainy country), so the country varies
# through the theme's place list — 36 places across 29 countries.
REEL_TOPICS = [
    {"topic": "turquoise bay from above", "search": "turquoise bay aerial drone boats", "angle": "una bahía turquesa vista desde el cielo", "angle_en": "a turquoise bay seen from the sky", "places": [
        {"name": "Bora Bora", "country": "French Polynesia", "match": "bora bora"},
        {"name": "Maya Bay", "country": "Thailand", "match": "maya bay"},
        {"name": "Grace Bay", "country": "Turks and Caicos Islands", "match": "grace bay"}]},
    {"topic": "tropical island escape", "search": "tropical island aerial drone turquoise water", "angle": "una isla para desconectar de verdad", "angle_en": "an island to truly disconnect", "places": [
        {"name": "Bali", "country": "Indonesia", "match": "bali"},
        {"name": "Santorini", "country": "Greece", "match": "santorini"},
        {"name": "Maui", "country": "United States", "match": "maui"}]},
    {"topic": "hidden beach", "search": "hidden beach paradise aerial drone", "angle": "una playa escondida que pocos conocen", "angle_en": "a hidden beach few people know", "places": [
        {"name": "Navagio Beach", "country": "Greece", "match": "navagio"},
        {"name": "Playa del Amor", "country": "Mexico", "match": "amor"},
        {"name": "Anse Source d'Argent", "country": "Seychelles", "match": "argent"}]},
    {"topic": "palm beach coast", "search": "palm trees beach aerial ocean", "angle": "el paraíso cabe en una playa de palmeras", "angle_en": "paradise fits on a palm beach", "places": [
        {"name": "Tulum", "country": "Mexico", "match": "tulum"},
        {"name": "Waikiki", "country": "United States", "match": "waikiki"},
        {"name": "Copacabana", "country": "Brazil", "match": "copacabana"}]},
    {"topic": "ocean cliffs coast", "search": "ocean cliffs aerial drone coast", "angle": "el mar golpeando los acantilados", "angle_en": "the sea crashing against the cliffs", "places": [
        {"name": "Cliffs of Moher", "country": "Ireland", "match": "moher"},
        {"name": "Big Sur", "country": "United States", "match": "big sur"},
        {"name": "Twelve Apostles", "country": "Australia", "match": "twelve apostles"}]},
    {"topic": "coastal road trip", "search": "coastal road aerial ocean drive", "angle": "una ruta costera para viajar despacio", "angle_en": "a coastal road to travel slowly", "places": [
        {"name": "Amalfi Coast", "country": "Italy", "match": "amalfi"},
        {"name": "Great Ocean Road", "country": "Australia", "match": "great ocean road"},
        {"name": "Garden Route", "country": "South Africa", "match": "garden route"}]},
    {"topic": "a mountain lake at sunrise", "search": "mountain lake sunrise aerial", "angle": "un amanecer que vale la pena madrugar", "angle_en": "a sunrise worth waking up early for", "places": [
        {"name": "Lake Atitlán", "country": "Guatemala", "match": "atitlán"},
        {"name": "Lake Louise", "country": "Canada", "match": "louise"},
        {"name": "Lake Bled", "country": "Slovenia", "match": "bled"}]},
    {"topic": "waterfall adventure", "search": "waterfall jungle aerial drone", "angle": "perseguir cascadas, no likes", "angle_en": "chasing waterfalls, not likes", "places": [
        {"name": "Plitvice Lakes", "country": "Croatia", "match": "plitvice"},
        {"name": "Iguazu Falls", "country": "Argentina", "match": "iguazu"},
        {"name": "Victoria Falls", "country": "Zambia", "match": "victoria"}]},
    {"topic": "desert dunes", "search": "desert dunes sunset travel", "angle": "el silencio del desierto al atardecer", "angle_en": "the silence of the desert at sunset", "places": [
        {"name": "Wadi Rum", "country": "Jordan", "match": "wadi rum"},
        {"name": "Salar de Uyuni", "country": "Bolivia", "match": "uyuni"},
        {"name": "Namib Desert", "country": "Namibia", "match": "namib"}]},
    {"topic": "old town streets", "search": "old town europe streets travel", "angle": "perderse por calles antiguas sin prisa", "angle_en": "getting lost in old streets, no rush", "places": [
        {"name": "Hallstatt", "country": "Austria", "match": "hallstatt"},
        {"name": "Antigua Guatemala", "country": "Guatemala", "match": "antigua"},
        {"name": "Chefchaouen", "country": "Morocco", "match": "chefchaouen"}]},
    {"topic": "forest hiking trail", "search": "forest hiking trail aerial", "angle": "caminar entre árboles para volver a respirar", "angle_en": "walking among trees to breathe again", "places": [
        {"name": "Black Forest", "country": "Germany", "match": "black forest"},
        {"name": "Redwood National Park", "country": "United States", "match": "redwood"},
        {"name": "Arashiyama", "country": "Japan", "match": "arashiyama"}]},
    {"topic": "night sky stars", "search": "milky way night sky mountains", "angle": "dormir bajo las estrellas", "angle_en": "sleeping under the stars", "places": [
        {"name": "Lofoten Islands", "country": "Norway", "match": "lofoten"},
        {"name": "Atacama Desert", "country": "Chile", "match": "atacama"},
        {"name": "Faroe Islands", "country": "Denmark", "match": "faroe"}]},
]

# 2026-11-07: reels were Spanish-only because this prompt and the TTS
# voice were hardcoded to Spanish (the text posts are in English). The
# language is now picked per run (pick_language) and both prompts exist.
SCRIPT_SYSTEM_ES = """Eres el guionista de "Wanderwithzen".
Escribes guiones cortos y apasionantes para Reels de 60 segundos sobre viajes, naturaleza y aventura consciente.

ESTRUCTURA OBLIGATORIA:
- Gancho inicial (5 seg): frase impactante que engancha de inmediato
- Desarrollo (40 seg): 3-4 datos fascinantes e interesantes
- Cierre (10 seg): pregunta que invite a comentar

REGLAS:
- Español conversacional y energético
- NUNCA copies letras de canciones
- Sin indicaciones de escena, sin paréntesis, solo el texto a narrar
- EXACTAMENTE entre 130 y 150 palabras"""

SCRIPT_SYSTEM_EN = """You are the scriptwriter for "Wanderwithzen".
You write short, gripping scripts for 60-second Reels about travel, nature and mindful adventure.

REQUIRED STRUCTURE:
- Opening hook (5 sec): a striking line that grabs attention at once
- Main part (40 sec): 3-4 fascinating, interesting facts
- Close (10 sec): a question that invites comments

RULES:
- Conversational, energetic English
- NEVER copy song lyrics
- No scene directions, no parentheses, just the narration text
- EXACTLY between 130 and 150 words"""


def pick_topic() -> dict:
    now = datetime.now(timezone.utc)
    # One topic per UTC day (not one per ISO week), so daily workflow stays varied.
    day_index = int(now.timestamp() // 86400)
    topic = dict(REEL_TOPICS[day_index % len(REEL_TOPICS)])
    # One place per run, picked at random from the theme's three places
    # in three different countries, so the country varies run to run.
    place = random.choice(topic.pop("places"))
    topic["place"] = place["name"]
    topic["country"] = place["country"]
    topic["match"] = place["match"]
    return topic


def pick_language() -> str:
    # Reels were Spanish-only; pick Spanish or English at random per run
    # so the feed is not limited to one language.
    return random.choice(["es", "en"])


def _normalize_text(text: str) -> str:
    import unicodedata

    nfkd = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _ensure_place_mentioned(script: str, topic_data: dict, lang: str = "es") -> str:
    # 2026-11-07: the reel must name its real place and country, the same
    # rule as the text posts. Groq usually follows the prompt, but if the
    # place never made it into the script, close with a line that names
    # it instead of publishing a placeless reel.
    place = topic_data.get("place", "")
    country = topic_data.get("country", "")
    if not place:
        return script
    # Check the distinctive word ("match"), not the full English name —
    # the script is in Spanish and may say "el lago Atitlán" rather than
    # "Lake Atitlán". Same convention as REAL_PLACES in content_generator.
    match = topic_data.get("match", place)
    if _normalize_text(match) in _normalize_text(script):
        return script
    print(f"  Place '{place}' not mentioned in script — appending closing line.")
    if lang == "es":
        return script.rstrip() + f" Todo esto te espera en {place}, {country}."
    return script.rstrip() + f" All of this is waiting for you in {place}, {country}."


def generate_script(topic_data: dict, lang: str = "es") -> str:
    # 2026-11-07: Groq sometimes returns an empty (0-word) script. The old
    # code accepted it, Kokoro then produced no audio, make_reel quit
    # quietly and the whole workflow still showed green with no reel.
    # Retry up to 3 times and fail loudly instead of passing an empty
    # script down the line.
    # 2026-11-07, second failure: the same prompt came back empty 3 times
    # in a row, so it is not a transient hiccup. Likely cause: gpt-oss is
    # a reasoning model, and max_tokens covers its reasoning budget too —
    # the "count the words first" instruction burns the 400-token budget
    # on reasoning and leaves nothing for the script itself (the text
    # posts, same key and model but max_tokens=800 and no counting
    # demand, worked minutes earlier). So: a much bigger token budget,
    # a lower temperature, and a non-reasoning fallback model on the
    # last attempt.
    client = Groq(api_key=GROQ_API_KEY)
    angle = topic_data["angle"] if lang == "es" else topic_data["angle_en"]
    if lang == "es":
        prompt = (
            f"Escribe un guión de Reel de 60 segundos sobre: {topic_data['topic']}\n"
            f"Ángulo: {angle}\n\n"
            f"Este guión DEBE tratar sobre este lugar real: {topic_data['place']}, {topic_data['country']}. "
            f"Menciona el lugar y el país por su nombre en el guión. "
            f"OBLIGATORIO: escribe EXACTAMENTE entre 140 y 155 palabras. "
            f"Cuenta las palabras antes de responder. "
            f"Si tienes menos de 140 palabras, agrega más detalles y ejemplos. "
            f"Solo el texto a narrar, sin indicaciones de escena."
        )
    else:
        prompt = (
            f"Write a 60-second Reel script about: {topic_data['topic']}\n"
            f"Angle: {angle}\n\n"
            f"This script MUST be about this real place: {topic_data['place']}, {topic_data['country']}. "
            f"Mention the place and the country by name in the script. "
            f"MANDATORY: write EXACTLY between 140 and 155 words. "
            f"Count the words before answering. "
            f"If you have fewer than 140 words, add more details and examples. "
            f"Only the narration text, no scene directions."
        )
    last_error = ""
    for attempt in range(1, 5):
        # Attempts 1-2 and 4: gpt-oss-120b (the primary model). Attempt 3:
        # openai/gpt-oss-20b — the smaller, faster model in the same family.
        # 2026-11-07: the old attempt-3 fallback, llama-3.3-70b-versatile,
        # 404s ("does not exist or you do not have access") — Groq's docs
        # now list it as Enterprise, and the only other non-reasoning
        # production model (llama-3.1-8b-instant) carries the same badge,
        # so the verified fallback is gpt-oss-20b (Production, developer
        # plan, per https://console.groq.com/docs/models 2026-11-07).
        model = "openai/gpt-oss-20b" if attempt == 3 else "openai/gpt-oss-120b"
        script = ""
        try:
            completion = client.chat.completions.create(
                model       = model,
                messages    = [
                    {"role": "system", "content": SCRIPT_SYSTEM_ES if lang == "es" else SCRIPT_SYSTEM_EN},
                    {"role": "user",   "content": prompt},
                ],
                temperature = 0.7,
                max_tokens  = 2000,
            )
            script = completion.choices[0].message.content.strip()
        except Exception as e:
            last_error = str(e)
            print(f"  Script attempt {attempt} ({model}) error: {e}")
        words = len(script.split())
        if words >= 120:
            return _ensure_place_mentioned(script, topic_data, lang)
        print(f"  Script attempt {attempt} ({model}) returned {words} words — retrying...")
        last_error = last_error or f"only {words} words"
        time.sleep(5)
    raise RuntimeError(f"Script generation failed after 4 attempts (last: {last_error})")


def text_to_speech_kokoro(script: str, output_path: str, lang: str = "es") -> str | None:
    """
    Generate voiceover using Kokoro TTS.
    Kokoro is 100% free, open-source, runs locally — no API key needed.
    Install: pip install kokoro soundfile
    """
    try:
        from kokoro import KPipeline
        import soundfile as sf
        import numpy as np

        print("  Loading Kokoro TTS (first run downloads ~500MB model)...")
        # Kokoro's KPipeline takes a single-letter code ('e' = Spanish,
        # 'a' = American English). 'es' only works because it is an alias
        # for 'e'; 'en' is not an alias for anything, so passing 'en'
        # raises (2026-11-07 run). Verified against kokoro 0.9.4 source.
        kokoro_lang = "e" if lang == "es" else "a"
        pipeline = KPipeline(lang_code=kokoro_lang)
        voice = "ef_dora" if lang == "es" else "af_heart"  # Spanish / English female voice

        # Generate audio — Kokoro returns audio chunks
        audio_chunks = []
        for chunk in pipeline(script, voice=voice):
            if chunk.audio is not None:
                audio_chunks.append(chunk.audio)

        if not audio_chunks:
            print("  Kokoro returned no audio.")
            return False

        # Concatenate chunks and save as WAV
        audio = np.concatenate(audio_chunks)
        sf.write(output_path, audio, 24000)
        print(f"  Audio saved: {output_path}")
        return output_path

    except ImportError:
        print("  Kokoro not installed. Run: pip install kokoro soundfile")
        print("  Falling back to gTTS (Google TTS, also free)...")
        return text_to_speech_gtts(script, output_path, lang)
    except Exception as e:
        print(f"  Kokoro error: {e}")
        print("  Falling back to gTTS...")
        return text_to_speech_gtts(script, output_path, lang)


def text_to_speech_gtts(script: str, output_path: str, lang: str = "es") -> str | None:
    """
    Fallback: Google Text-to-Speech (gTTS) — free, no API key.
    Quality is lower than Kokoro but works everywhere.
    Install: pip install gtts
    """
    try:
        from gtts import gTTS
        # gTTS always outputs MP3 bytes. Do NOT save them to a .wav path.
        # Use .mp3 so downstream (MoviePy) can decode correctly.
        mp3_path = output_path
        if mp3_path.lower().endswith(".wav"):
            mp3_path = mp3_path[:-4] + ".mp3"
        tts = gTTS(text=script, lang=lang, slow=False)
        tts.save(mp3_path)
        print(f"  Audio saved via gTTS: {mp3_path}")
        return mp3_path
    except ImportError:
        print("  gTTS not installed. Run: pip install gtts")
        return None
    except Exception as e:
        print(f"  gTTS error: {e}")
        return None


def get_pexels_videos(query: str, count: int = 6) -> list:
    # 2026-11-07: the same query that found clips in the morning returned
    # 0 videos in the afternoon run ("ocean cliffs aerial drone coast").
    # Pexels is picky with long multi-word queries and can come back empty
    # for no clear reason, so retry with progressively simpler queries
    # before giving up.
    if not PEXELS_KEY:
        print("  PEXELS_API_KEY not set.")
        return []
    words = query.split()
    # Each attempt is (query, orientation). The last one is the broadest
    # possible: the first word alone, with no orientation filter — the
    # assembler center-crops landscape clips to vertical anyway, so a
    # landscape ocean clip is still usable. (2026-11-07: even "ocean
    # cliffs" came back empty in the 17:32 UTC run, so the fallback has
    # to go wider than two words.)
    attempts = [(query, "portrait")]
    if len(words) > 3:
        attempts.append((" ".join(words[:3]), "portrait"))
    if len(words) > 2:
        attempts.append((" ".join(words[:2]), "portrait"))
    if len(words) > 1:
        attempts.append((words[0], None))
    for round_no in (1, 2):
        for q, orientation in attempts:
            try:
                params = {
                    "query":    q,
                    "per_page": 15,
                    "size":     "medium",
                }
                if orientation:
                    params["orientation"] = orientation
                r = requests.get(
                    "https://api.pexels.com/videos/search",
                    headers={"Authorization": PEXELS_KEY},
                    params=params,
                    timeout=15,
                )
                r.raise_for_status()
                videos = r.json().get("videos", [])
                if not videos:
                    print(f"  Pexels: no videos for '{q}' — trying a simpler query...")
                    time.sleep(3)
                    continue
                urls = []
                sample = random.sample(videos, min(count, len(videos)))
                for v in sample:
                    files = sorted(
                        [f for f in v["video_files"] if f.get("quality") in ("hd", "sd")],
                        key=lambda x: x.get("width", 0),
                    )
                    if files:
                        # Prefer the highest-resolution variant for better final quality.
                        urls.append(files[-1]["link"])
                return urls
            except Exception as e:
                print(f"  Pexels video error for '{q}': {e}")
                time.sleep(3)
        if round_no == 1:
            print("  Pexels: every query came back empty — waiting 60s and trying the whole ladder once more...")
            time.sleep(60)
    return []


def get_commons_videos(query: str, count: int = 6) -> list:
    # 2026-11-07: Pexels video search came back empty for three straight
    # runs even for the broadest query ("ocean"), so the reel no longer
    # depends on Pexels alone. Wikimedia Commons is keyless and has real
    # drone/coast footage (e.g. "Cliffs of Moher drone-video.webm").
    # The filetype:video search filter is what finds videos — a plain
    # File-namespace search returns mostly photos. The playable file is
    # NOT imageinfo's thumburl (that is a JPG poster frame) but a
    # videoinfo derivative under /transcoded/ — take the widest one at or
    # below 854px, so the download stays small; the assembler center-crops
    # to vertical anyway. The assembler saves each clip with a .mp4 name
    # but ffmpeg probes the content, so webm decodes fine.
    words = query.split()
    queries = [query]
    if len(words) > 2:
        queries.append(" ".join(words[:2]))
    if len(words) > 1:
        queries.append(words[0])
    found, seen = [], set()
    for q in queries:
        try:
            r = requests.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "generator": "search",
                    "gsrsearch": f"{q} filetype:video",
                    "gsrnamespace": 6,
                    "gsrlimit": 15,
                    "prop": "imageinfo|videoinfo",
                    "iiprop": "url|size|mime",
                    "viprop": "derivatives",
                    "viurlwidth": 1280,
                },
                headers={"User-Agent": "WanderwithzenBot/1.0"},
                timeout=20,
            )
            r.raise_for_status()
            pages = (r.json().get("query") or {}).get("pages", {})
            urls = []
            for pg in pages.values():
                ii = (pg.get("imageinfo") or [{}])[0]
                mime = ii.get("mime") or ""
                if not (mime.startswith("video/") or mime == "application/ogg"):
                    continue
                url = None
                derivatives = (pg.get("videoinfo") or [{}])[0].get("derivatives") or []
                sized = [d for d in derivatives if d.get("src") and d.get("width")]
                if sized:
                    small = [d for d in sized if d["width"] <= 854]
                    pick = max(small, key=lambda d: d["width"]) if small else min(sized, key=lambda d: d["width"])
                    url = pick["src"]
                elif ii.get("url") and (ii.get("size") or 0) <= 200_000_000:
                    url = ii["url"]
                if url:
                    urls.append(url)
            # Accumulate across the ladder instead of stopping at the
            # first hit: the full query may return a single clip (the
            # 23:55 UTC run found exactly 1), and one clip is one
            # download failure away from no reel at all. Narrow queries
            # feed the pool first; stop once we have enough.
            for url in urls:
                if url not in seen:
                    seen.add(url)
                    found.append(url)
            if not urls:
                print(f"  Commons: no videos for '{q}' — trying a simpler query...")
                time.sleep(3)
            if len(found) >= count:
                break
        except Exception as e:
            print(f"  Commons video error for '{q}': {e}")
            time.sleep(3)
    if not found:
        return []
    return random.sample(found, min(count, len(found)))


def _retry_after_seconds(response) -> int:
    # Wikimedia's 429s carry a Retry-After header (seconds, or an
    # HTTP-date). Honor it instead of guessing: wait at least 10s and
    # at most 120s so a run never stalls for minutes on one clip.
    raw = (response.headers or {}).get("Retry-After") if response is not None else None
    if raw is None:
        return 10
    try:
        return max(10, min(120, int(raw)))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        from datetime import datetime, timezone
        when = parsedate_to_datetime(raw)
        if when is not None:
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            delta = (when - datetime.now(timezone.utc)).total_seconds()
            return max(10, min(120, int(delta)))
    except Exception:
        pass
    return 10


def download_file(url: str, path: str) -> bool:
    # upload.wikimedia.org returns 403 for the default python-requests
    # User-Agent, so every download carries the bot's UA (2026-11-07).
    # It also rate-limits (429) under bursts: on a 429, wait out the
    # server's Retry-After header instead of a fixed 10s (2026-11-07:
    # the runner's Commons download 429'd on all 3 attempts 10s apart).
    for attempt in range(1, 4):
        try:
            r = requests.get(url, timeout=60, stream=True,
                             headers={"User-Agent": "WanderwithzenBot/1.0"})
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
        except Exception as e:
            wait = 10
            resp = getattr(e, "response", None)
            if resp is not None and getattr(resp, "status_code", None) == 429:
                wait = _retry_after_seconds(resp)
                print(f"  Download error (attempt {attempt}/3): {e} — server asked to wait {wait}s")
            else:
                print(f"  Download error (attempt {attempt}/3): {e}")
            if attempt < 3:
                time.sleep(wait)
    return False


def download_clips(video_urls: list, clips_dir) -> list:
    # Download every remote URL, skipping failures; local files pass
    # through. If NOTHING downloaded (e.g. Wikimedia 429'd every clip),
    # wait 60s and try the failed URLs once more — a per-minute
    # rate-limit bucket often clears in that time. 2026-11-07: the
    # 23:55 UTC run found 1 Commons clip and its download 429'd 3
    # times, so the reel died with no clip to try.
    def _once(urls):
        paths, failed = [], []
        for i, src in enumerate(urls):
            if src.startswith("http://") or src.startswith("https://"):
                tmp = str(clips_dir / f"clip_{i}.mp4")
                if download_file(src, tmp):
                    paths.append(tmp)
                else:
                    failed.append((i, src))
            elif os.path.exists(src):
                paths.append(src)
            else:
                print(f"    Skipping invalid source: {src}")
        return paths, failed
    clip_paths, failed = _once(video_urls)
    if not clip_paths and failed:
        print("  No clips downloaded — waiting 60s and retrying the downloads once more...")
        time.sleep(60)
        retry_paths, _ = _once([src for _, src in failed])
        clip_paths.extend(retry_paths)
    return clip_paths


def download_youtube_video(video_url: str, output_path: str) -> bool:
    if get_video_for_topic is None:
        print("  YouTube download helper unavailable.")
        return False
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        print("  yt-dlp not installed. Install with: pip install yt_dlp")
        return False

    print(f"  Downloading YouTube footage: {video_url}")
    ydl_opts = {
        "format": "best[ext=mp4]+bestaudio/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return os.path.exists(output_path)
    except Exception as e:
        print(f"  yt-dlp error: {e}")
        return False


def get_youtube_clips(topic: str, count: int = 2) -> list:
    if get_video_for_topic is None:
        return []
    clips = []
    used_ids = []
    for _ in range(count):
        video = get_video_for_topic(topic, used_ids)
        if not video:
            break
        video_id = video["url"].split("v=")[-1].split("&")[0]
        used_ids.append(video_id)
        filename = OUTPUT_DIR / f"yt_clip_{video_id}.mp4"
        if filename.exists() or download_youtube_video(video["url"], str(filename)):
            clips.append(str(filename))
        else:
            break
    return clips


def add_hook_overlay(input_path: str, hook_text: str, output_path: str) -> bool:
    """
    Burn the hook line (the topic angle) onto the first 5 seconds of the
    reel, like the on-screen text on @wanderwithzen's reels ("Exciting
    news!", "4 things you ..."). Fail-soft: any problem leaves the
    original file untouched and returns False.
    """
    import subprocess

    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not hook_text or not hook_text.strip() or not os.path.exists(font):
        return False
    words = hook_text.strip().split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + len(w) + 1 > 24:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    textfile = os.path.join(tempfile.gettempdir(), "wander_hook.txt")
    try:
        with open(textfile, "w", encoding="utf-8") as f:
            f.write("\n".join(lines[:3]))
    except Exception as e:
        print(f"  Hook overlay: could not write text file: {e}")
        return False
    vf = (
        f"drawtext=textfile='{textfile}':fontfile={font}:fontsize=54:"
        f"fontcolor=white:borderw=2:bordercolor=black:"
        f"x=(w-text_w)/2:y=h*0.72:enable='between(t,0,5)'"
    )
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-vf", vf,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
             "-c:a", "copy", output_path],
            capture_output=True, text=True, timeout=600,
        )
        if r.returncode == 0 and os.path.exists(output_path):
            return True
        print(f"  Hook overlay failed: {r.stderr[-300:]}")
        return False
    except Exception as e:
        print(f"  Hook overlay error: {e}")
        return False


def assemble_reel(audio_path: str, video_urls: list, output_path: str, hook_text: str | None = None) -> bool:
    try:
        # Patch Pillow ANTIALIAS removal (Pillow 10+ removed it, MoviePy 1.0.3 needs it)
        import PIL.Image as _PILImage
        if not hasattr(_PILImage, "ANTIALIAS"):
            _PILImage.ANTIALIAS = _PILImage.LANCZOS

        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip

        TARGET_W, TARGET_H = 1080, 1920

        narration_audio = AudioFileClip(audio_path)
        duration = narration_audio.duration + 1.0
        print(f"  Narration duration: {duration:.1f}s")

        # Download clips to a permanent temp folder (avoids Windows file-locking issue)
        clips_dir = OUTPUT_DIR / "tmp_clips"
        clips_dir.mkdir(exist_ok=True)

        clip_paths = download_clips(video_urls, clips_dir)

        clips = []
        for i, path in enumerate(clip_paths):
            try:
                clip  = VideoFileClip(path)
                ratio = clip.w / clip.h
                tgt   = TARGET_W / TARGET_H
                if ratio > tgt:
                    new_w = int(clip.h * tgt)
                    clip  = clip.crop(x1=(clip.w - new_w) // 2, width=new_w)
                else:
                    new_h = int(clip.w / tgt)
                    clip  = clip.crop(y1=(clip.h - new_h) // 2, height=new_h)
                clip = clip.resize((TARGET_W, TARGET_H))
                clip = clip.subclip(0, min(clip.duration, 10.0))
                clips.append(clip)
                print(f"    Clip {i} OK ({clip.duration:.1f}s)")
            except Exception as e:
                print(f"    Clip {i} error: {e}")

        if not clips:
            print("  No valid clips — cannot assemble Reel.")
            narration_audio.close()
            shutil.rmtree(clips_dir, ignore_errors=True)
            return False

        # Loop clips to fill audio duration
        while sum(c.duration for c in clips) < duration:
            clips.extend(clips[:])
        clips = clips[:20]

        video = concatenate_videoclips(clips, method="compose")
        video = video.subclip(0, min(duration, video.duration))

        # Prefer actual clip audio when available, otherwise use narration only.
        if video.audio is not None:
            print("  Using actual clip audio with narration overlay.")
            clip_audio = video.audio.volumex(0.65)
            narration = narration_audio.volumex(1.0).set_duration(video.duration)
            mixed_audio = CompositeAudioClip([clip_audio, narration])
            mixed_audio = mixed_audio.set_duration(video.duration)
            video = video.set_audio(mixed_audio)
        else:
            print("  No clip audio found; using narration only.")
            video = video.set_audio(narration_audio)

        video.write_videofile(
            output_path,
            fps         = 30,
            codec       = "libx264",
            audio_codec = "aac",
            bitrate     = "4000k",
            verbose     = False,
            logger      = None,
        )
        video.close()
        narration_audio.close()

        # On-screen hook text for the first 5 seconds (the @wanderwithzen style).
        if hook_text:
            hooked = output_path + ".hooked.mp4"
            if add_hook_overlay(output_path, hook_text, hooked):
                os.replace(hooked, output_path)
                print("  Hook text overlay added.")
            else:
                print("  Hook text overlay skipped (original kept).")

        # Clean up temp clips after MoviePy has fully released file handles
        shutil.rmtree(clips_dir, ignore_errors=True)
        return True

    except ImportError:
        print("  MoviePy not installed. Run: pip install moviepy==1.0.3")
        return False
    except Exception as e:
        print(f"  Assembly error: {e}")
        return False


def make_reel():
    now        = datetime.now(timezone.utc)
    stamp      = now.strftime("%Y%m%d")
    topic_data = pick_topic()
    lang = pick_language()

    print(f"[{now.isoformat()}] Making Reel: {topic_data['topic']}")
    print(f"  Place: {topic_data['place']}, {topic_data['country']} | Language: {'Spanish' if lang == 'es' else 'English'}")
    print(f"  Angle: {topic_data['angle'] if lang == 'es' else topic_data['angle_en']}\n")

    # Step 1 — Script
    print("  Step 1: Writing script with Groq...")
    try:
        script = generate_script(topic_data, lang)
    except Exception as e:
        print(f"  Step 1 FAILED: {e}")
        raise SystemExit(1)
    print(f"  Script ({len(script.split())} words):\n  {script[:120]}...\n")

    script_path = OUTPUT_DIR / f"reel_{stamp}_script.txt"
    script_path.write_text(
        f"Topic: {topic_data['topic']}\nAngle: {topic_data['angle']}\nPlace: {topic_data['place']}, {topic_data['country']}\nLanguage: {lang}\n\n{script}",
        encoding="utf-8"
    )

    # Step 2 — TTS (Kokoro first, gTTS fallback)
    audio_path = str(OUTPUT_DIR / f"reel_{stamp}_audio.wav")
    print(f"  Step 2: Generating {'Spanish' if lang == 'es' else 'English'} voiceover (Kokoro TTS)...")
    audio_file = text_to_speech_kokoro(script, audio_path, lang)

    if not audio_file:
        print("  Audio generation failed. Script saved for manual recording.")
        print(f"  Script: {script_path}")
        raise SystemExit(1)

    # Step 3 — Video clips: prefer actual artist footage and audio via YouTube, fallback to Pexels stock clips.
    print(f"\n  Step 3: Looking for actual footage and sound for '{topic_data['topic']}'...")
    video_urls = []
    if YOUTUBE_API_KEY and get_video_for_topic:
        video_urls = get_youtube_clips(topic_data["topic"], count=2)
        if video_urls:
            print(f"  Found {len(video_urls)} actual YouTube clip(s) with artist footage.")

    if not video_urls:
        print(f"  Step 3 fallback: Fetching Pexels clips ('{topic_data['search']}')...")
        video_urls = get_pexels_videos(topic_data["search"], count=6)
        print(f"  Found {len(video_urls)} stock clips.")

    if not video_urls:
        print(f"  Step 3 fallback: Fetching Wikimedia Commons clips ('{topic_data['search']}')...")
        video_urls = get_commons_videos(topic_data["search"], count=6)
        print(f"  Found {len(video_urls)} Commons clips.")

    if not video_urls:
        # Fail loudly: the audio is saved for manual editing, but the
        # automated reel did not happen, so the run must show red.
        print("  No clips found. Audio saved — edit manually in CapCut.")
        raise SystemExit(1)

    # Step 4 — Assemble
    output_path = str(OUTPUT_DIR / f"reel_{stamp}.mp4")
    print(f"\n  Step 4: Assembling Reel with MoviePy...")
    ok = assemble_reel(audio_file, video_urls, output_path, hook_text=topic_data["angle"] if lang == "es" else topic_data["angle_en"])

    if ok:
        mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"\n  Reel ready: {output_path} ({mb:.1f} MB)")
        print(f"  Script:     {script_path}\n")

        # Step 5 — Upload to YouTube as a Short
        # CI: set GitHub secrets YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
        _yt_ci = _youtube_env_configured()
        if os.getenv("GITHUB_ACTIONS", "").lower() == "true" and not _yt_ci:
            print(
                "  Step 5: YouTube Short skipped in Actions — add secrets "
                "YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN "
                "(run locally: python make_reel.py --auth after deleting youtube_token.json)."
            )
        else:
            print("  Step 5: Uploading to YouTube as a Short...")
            yt_url = upload_youtube_short(output_path, topic_data, script)
            if yt_url:
                print(f"  YouTube Short: {yt_url}")
            else:
                print(
                    "  YouTube Short: skipped (set env YouTube OAuth trio, or youtube_client_secret.json + youtube_token.json, or run make_reel.py --auth)"
                )

        print(f"\n  Manual upload still needed for:")
        print(f"  → Facebook: Open app → Reel → upload reel_{stamp}.mp4")
        print(f"  → Instagram Reel: Open app → + → Reel → upload reel_{stamp}.mp4")
        print(f"  → TikTok: Open app → + → upload reel_{stamp}.mp4")
    else:
        print(f"\n  Assembly failed. Audio at: {audio_path}")
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# YouTube Shorts upload
# ---------------------------------------------------------------------------

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def _youtube_env_configured() -> bool:
    return all(
        os.getenv(k, "").strip()
        for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
    )


def _credentials_from_env() -> object | None:
    """Non-interactive OAuth for CI: refresh token + client id/secret."""
    cid = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
    csec = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
    rt = os.getenv("YOUTUBE_REFRESH_TOKEN", "").strip()
    if not (cid and csec and rt):
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = Credentials(
            token=None,
            refresh_token=rt,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=cid,
            client_secret=csec,
            scopes=[YOUTUBE_UPLOAD_SCOPE],
        )
        creds.refresh(Request())
        return creds
    except Exception as e:
        print(f"  YouTube env credentials error: {e}")
        return None


def _credentials_from_files() -> object | None:
    """Local: youtube_client_secret.json + youtube_token.json (pickle)."""
    import pickle

    client_secret_file = "youtube_client_secret.json"
    token_file = "youtube_token.json"
    if not os.path.exists(client_secret_file):
        return None
    try:
        from google.auth.transport.requests import Request

        SCOPES = [YOUTUBE_UPLOAD_SCOPE]
        creds = None
        if os.path.exists(token_file):
            with open(token_file, "rb") as f:
                creds = pickle.load(f)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                print("  YouTube auth required — run: python make_reel.py --auth")
                return None
            with open(token_file, "wb") as f:
                pickle.dump(creds, f)
        return creds
    except Exception as e:
        print(f"  YouTube file credentials error: {e}")
        return None


def upload_youtube_short(video_path, topic_data, script):
    """
    Upload the assembled Reel as a YouTube Short.
    Uses YouTube Data API v3 with OAuth2.

    **GitHub Actions:** set env `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`,
    `YOUTUBE_REFRESH_TOKEN` (get refresh token via `python make_reel.py --auth` locally).

    **Local file flow:**
    1. Save OAuth client JSON as youtube_client_secret.json
    2. Run: python make_reel.py --auth  (opens browser once)
    3. Saves youtube_token.json
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = _credentials_from_env() or _credentials_from_files()
        if not creds:
            return None

        youtube = build("youtube", "v3", credentials=creds)

        # Build title and description
        title       = "Wanderwithzen: " + topic_data["topic"] + " #Shorts"
        description = script + "\n\n#Wanderwithzen #Travel #Shorts #" + topic_data["topic"].replace(" ", "")

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title":       title[:100],
                    "description": description[:5000],
                    "tags":        ["travel", "nature", "wanderwithzen", topic_data["topic"], "shorts"],
                    "categoryId":  "19",   # Travel & Events
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                },
            },
            media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True),
        )

        print("  Uploading to YouTube (this may take a minute)...")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"    Upload: {pct}%")

        video_id = response.get("id", "")
        return "https://youtube.com/shorts/" + video_id if video_id else None

    except ImportError:
        print("  YouTube upload libs not installed. Run:")
        print("  pip install google-api-python-client google-auth-oauthlib")
        return None
    except Exception as e:
        print(f"  YouTube upload error: {e}")
        return None


def run_auth():
    """One-time OAuth flow to authorize YouTube uploads. Run: python make_reel.py --auth"""
    import pickle
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        SCOPES = [YOUTUBE_UPLOAD_SCOPE]
        flow = InstalledAppFlow.from_client_secrets_file("youtube_client_secret.json", SCOPES)
        # offline + consent so Google returns a refresh_token (needed for CI / non-interactive refresh)
        creds = flow.run_local_server(
            port=0,
            access_type="offline",
            prompt="consent",
        )
        with open("youtube_token.json", "wb") as f:
            pickle.dump(creds, f)
        print("YouTube authorization complete! Token saved to youtube_token.json\n")
        if creds.refresh_token:
            print("--- Copy into GitHub Actions secret: YOUTUBE_REFRESH_TOKEN ---")
            print(creds.refresh_token)
            print("--- Also add YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET from the same OAuth client (Google Cloud Console → Credentials). ---\n")
        else:
            print(
                "WARNING: No refresh_token returned. Delete youtube_token.json and run --auth again,\n"
                "or revoke the app's access in your Google account and retry.\n"
            )
    except Exception as e:
        print(f"Auth error: {e}")


if __name__ == "__main__":
    import sys
    if "--auth" in sys.argv:
        run_auth()
    else:
        make_reel()

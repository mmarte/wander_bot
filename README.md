# WanderWithZen Content Bot

A travel and adventure social media content generation bot for short-form formats like reels, stories, and shorts.

## What this project includes

- `wander_bot/content_generator.py` — generates travel/adventure captions, video ideas, hashtags, and short-form content outlines.
- `wander_bot/platforms.py` — platform poster interfaces and placeholder adapter examples for Facebook, Instagram, TikTok, YouTube, X, and Threads.
- `wander_bot/bot.py` — orchestrates generation and posting.
- `run_bot.py` — CLI entry point.

## Features

- Focus on travel, nature, and adventure.
- Designed for reels/stories/shorts.
- Supports generation for multiple platforms with a unified content model.
- Includes sample placeholder posting flows for platform APIs.

## Getting started

1. Create a Python virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and add your API keys and tokens.

3. Generate content:

```powershell
python run_bot.py --action generate --platform instagram --count 3
```

4. Publish content using the supported platform adapters:

```powershell
python run_bot.py --action publish --platform facebook --input content.json --media C:\path\to\video.mp4
```

## Environment variables

- `OPENAI_API_KEY`
- `FACEBOOK_PAGE_ACCESS_TOKEN`
- `INSTAGRAM_BUSINESS_ACCOUNT_ID`
- `X_BEARER_TOKEN`
- `TIKTOK_ACCESS_TOKEN`
- `TIKTOK_OPEN_ID`
- `YOUTUBE_ACCESS_TOKEN`
- `THREADS_AUTH_TOKEN`
- `THREADS_USER_ID`

## Notes

- Real posting now includes actual API request flows for Facebook, Instagram, TikTok, YouTube, X, and Threads.
- Instagram reels upload requires a publicly accessible `video_url`.
- YouTube upload requires an OAuth Bearer token, not just an API key.
- X upload uses the legacy media upload endpoints and requires a valid bearer token with tweet publishing permissions.
- Threads posting uses the Threads Graph API base endpoints and requires `threads_content_publish` permission.
- Some platforms may still require additional setup or developer approval before posting on behalf of your account.

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from wander_bot.bot import WanderBot


def parse_args():
    parser = argparse.ArgumentParser(description="WanderWithZen content bot for travel and adventure short-form posts.")
    parser.add_argument("--action", choices=["generate", "publish"], default="generate", help="Action to perform.")
    parser.add_argument("--platform", default="instagram", help="Target social platform, or all when publishing.")
    parser.add_argument("--location", default="a mountain lake", help="Location or travel theme for content generation.")
    parser.add_argument("--count", type=int, default=1, help="Number of ideas to generate.")
    parser.add_argument("--media", type=str, default=None, help="Local media file path for posting.")
    parser.add_argument("--input", type=str, default=None, help="JSON file path with content to publish.")
    return parser.parse_args()


def main():
    args = parse_args()
    bot = WanderBot()

    if args.action == "generate":
        ideas = bot.generate(args.location, platform=args.platform, count=args.count)
        queue_path = Path("posts.json")
        posts = []
        if queue_path.exists():
            try:
                posts = json.loads(queue_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                posts = []
        for idea in ideas:
            idea.update({
                "id": f"wander-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "brand": "Wanderwithzen",
                "page_id": "61589349864879",
            })
            posts.append(idea)
        queue_path.write_text(json.dumps(posts[-50:], ensure_ascii=False, indent=2), encoding="utf-8")
        for index, idea in enumerate(ideas, start=1):
            print(f"\n=== Idea {index} ===")
            for key, value in idea.items():
                print(f"{key}: {value}")

    elif args.action == "publish":
        path = Path(args.input or "posts.json")
        if not path.exists():
            raise SystemExit(f"Input file not found: {args.input}")

        with path.open("r", encoding="utf-8") as handle:
            content = json.load(handle)

        posts = content if isinstance(content, list) else [content]
        pending = [post for post in posts if post.get("status") == "pending"]
        if not pending:
            print("No pending posts to publish.")
            return

        post = pending[0]
        platforms = [args.platform] if args.platform != "all" else [
            "facebook", "instagram", "x", "threads", "tiktok", "youtube"
        ]
        results = {}
        for platform in platforms:
            results[platform] = bot.publish(post, platform=platform, media_path=args.media)
        successful = [name for name, result in results.items() if result.get("status") == "ok"]
        post["status"] = "published" if successful else "failed"
        post["published_at"] = datetime.now(timezone.utc).isoformat() if successful else None
        post["publish_results"] = results
        path.write_text(json.dumps(posts[-50:], ensure_ascii=False, indent=2), encoding="utf-8")
        log_path = Path("log.json")
        logs = []
        if log_path.exists():
            try:
                logs = json.loads(log_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logs = []
        logs.append({"post_id": post.get("id"), "status": post["status"], "results": results,
                     "executed_at": datetime.now(timezone.utc).isoformat()})
        log_path.write_text(json.dumps(logs[-200:], ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"post_id": post.get("id"), "status": post["status"], "results": results}, ensure_ascii=False, indent=2))
        if not successful:
            raise SystemExit("No platform published the post.")


if __name__ == "__main__":
    main()

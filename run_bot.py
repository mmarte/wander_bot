import argparse
from pathlib import Path

from wander_bot.bot import WanderBot


def parse_args():
    parser = argparse.ArgumentParser(description="WanderWithZen content bot for travel and adventure short-form posts.")
    parser.add_argument("--action", choices=["generate", "publish"], default="generate", help="Action to perform.")
    parser.add_argument("--platform", default="instagram", help="Target social platform.")
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
        for index, idea in enumerate(ideas, start=1):
            print(f"\n=== Idea {index} ===")
            for key, value in idea.items():
                print(f"{key}: {value}")

    elif args.action == "publish":
        if not args.input:
            raise SystemExit("--input is required when action=publish")
        import json

        path = Path(args.input)
        if not path.exists():
            raise SystemExit(f"Input file not found: {args.input}")

        with path.open("r", encoding="utf-8") as handle:
            content = json.load(handle)

        result = bot.publish(content, platform=args.platform, media_path=args.media)
        print(result)


if __name__ == "__main__":
    main()

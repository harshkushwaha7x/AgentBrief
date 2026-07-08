from __future__ import annotations

import argparse
import json

from app.newsletter_agent.agent import DEFAULT_GOAL, run_newsletter_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the autonomous newsletter agent.")
    parser.add_argument("--goal", default=DEFAULT_GOAL, help="Plain English goal for the agent.")
    parser.add_argument(
        "--mode",
        choices=["autonomous", "human"],
        default="autonomous",
        help="Execution mode.",
    )
    parser.add_argument("--feedback", default=None, help="Optional human review feedback.")
    args = parser.parse_args()

    result = run_newsletter_agent(args.goal, mode=args.mode, human_feedback=args.feedback)

    print(f"Status: {result['status']}")
    print(f"Subject: {result.get('subject', '')}")
    if result.get("output_paths"):
        print("Saved files:")
        print(json.dumps(result["output_paths"], indent=2))
    print("\nTool log:")
    for entry in result.get("tool_log", []):
        print(f"- {entry}")

    if result["status"] == "needs_review":
        print("\nDraft Markdown:\n")
        print(result.get("markdown", ""))
    else:
        print("\nSimulated email content:\n")
        print(result.get("markdown", ""))


if __name__ == "__main__":
    main()

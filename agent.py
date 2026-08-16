"""OpenAI-powered agent that decides which Gmail cleanup actions to take."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

import gmail_client

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

MODEL = "gpt-4o-mini"
MAX_TOOL_ROUNDS = 2
MAX_SEARCH_RESULTS = 50

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_unread",
            "description": "List unread message IDs currently in the Gmail inbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of unread messages to fetch.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trash_unread_messages",
            "description": "Move all unread messages in the inbox to Trash.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "empty_trash",
            "description": "Permanently delete every message currently in Trash.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _dispatch(service, name, args):
    if name == "search_unread":
        requested = min(int(args.get("max_results", MAX_SEARCH_RESULTS)), MAX_SEARCH_RESULTS)
        ids = gmail_client.search_unread(service, requested)
        return {
            "unread_count": len(ids),
            "sample_ids": ids[:10],
        }
    if name == "trash_unread_messages":
        return gmail_client.trash_unread_messages(service)
    if name == "empty_trash":
        return gmail_client.empty_trash(service)
    return {"error": f"Unknown tool '{name}'"}


def run_agent(instruction: str):
    """Run one agent turn: send the instruction to OpenAI, execute any tool calls it requests."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Create a .env file in the project root and add:\n"
            "OPENAI_API_KEY=your_key_here\n"
            f"Project root: {PROJECT_ROOT}"
        )

    client = OpenAI(api_key=api_key)
    service = gmail_client.get_gmail_service()

    messages = [
        {
            "role": "system",
            "content": (
                "You are a Gmail cleanup agent. Use the tool calls to complete the request. "
                "Keep the task strict and brief."
            ),
        },
        {"role": "user", "content": instruction},
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            temperature=0,
            max_tokens=200,
        )
        choice = response.choices[0]

        if not choice.message.tool_calls:
            return choice.message.content

        messages.append(choice.message)

        for call in choice.message.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            result = _dispatch(service, call.function.name, args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                }
            )

    return "Stopped after reaching the maximum number of tool-call steps."

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
MAX_TOOL_ROUNDS = 15
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
            "name": "trash_unread_spam_messages",
            "description": "Move all unread and spam messages to Trash.",
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
    {
        "type": "function",
        "function": {
            "name": "list_recent_messages",
            "description": "List the most recent messages in the inbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of recent messages to fetch.",
                        "default": 10,
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_message_content",
            "description": "Get the content (from, subject, body) of a specific email by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The ID of the message to retrieve.",
                    }
                },
                "required": ["message_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send an email to a recipient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "The email address of the recipient.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "The subject of the email.",
                    },
                    "body": {"type": "string", "description": "The plain text content of the email body."},
                },
                "required": ["to", "subject", "body"],
            },
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
    if name == "trash_unread_spam_messages":
        return gmail_client.trash_unread_spam_messages(service)
    if name == "empty_trash":
        return gmail_client.empty_trash(service)
    if name == "list_recent_messages":
        count = min(int(args.get("max_results", 10)), MAX_SEARCH_RESULTS)
        ids = gmail_client.list_recent_messages(service, max_results=count)
        return {"message_ids": ids}
    if name == "get_message_content":
        message_id = args.get("message_id") or args.get("id") or args.get("messageId")
        if not message_id:
            return {"error": "Missing message_id in tool arguments", "args": args}
        return gmail_client.get_message_content(service, message_id=message_id)
    if name == "send_message":
        return gmail_client.send_message(
            service,
            to=args["to"],
            subject=args.get("subject", ""),
            body=args.get("body", ""),
        )
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
                "You are a helpful Gmail assistant. Use the available tools to answer the user's request. "
                "When asked to summarize emails, first list the recent message IDs, then get the content for each, "
                "and finally provide a concise summary of the emails to the user."
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

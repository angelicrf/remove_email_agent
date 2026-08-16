"""Gmail API wrapper: OAuth login, unread search, trash, and empty-trash operations."""
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Full mail scope is required to permanently delete messages from Trash.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/gmail.readonly", "https://mail.google.com/"]

# Build paths relative to this script's directory for robustness.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "credentials.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "token.json")


def has_required_scope(creds):
    if not creds:
        return False
    granted_scopes = set(creds.scopes or [])
    return set(SCOPES).issubset(granted_scopes)


def get_gmail_service():
    """Authenticate via OAuth (cached in token.json) and return a Gmail API service."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds and not has_required_scope(creds):
            os.remove(TOKEN_FILE)
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Missing '{CREDENTIALS_FILE}'. Download OAuth client credentials "
                    "from Google Cloud Console and place them in the project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def search_unread(service, max_results=500):
    """Return message IDs for all unread messages in the inbox."""
    message_ids = []
    request = service.users().messages().list(
        userId="me", q="is:unread", maxResults=min(max_results, 500)
    )
    while request is not None and len(message_ids) < max_results:
        response = request.execute()
        message_ids.extend(m["id"] for m in response.get("messages", []))
        request = service.users().messages().list_next(request, response)
    return message_ids[:max_results]


def search_spam(service, max_results=500):
    """Return message IDs for all unread messages in the spam folder."""
    message_ids = []
    request = service.users().messages().list(
        userId="me", q="is:spam", maxResults=min(max_results, 500)
    )
    while request is not None and len(message_ids) < max_results:
        response = request.execute()
        message_ids.extend(m["id"] for m in response.get("messages", []))
        request = service.users().messages().list_next(request, response)
    return message_ids[:max_results]

def list_message_ids(service, q=None, label_ids=None, max_results=None):
    """Return all message IDs matching the query, optionally limited to max_results."""
    message_ids = []
    request = service.users().messages().list(
        userId="me",
        q=q,
        labelIds=label_ids,
        maxResults=500,
    )

    while request is not None:
        response = request.execute()
        message_ids.extend(msg["id"] for msg in response.get("messages", []))
        if max_results is not None and len(message_ids) >= max_results:
            break
        request = service.users().messages().list_next(request, response)

    if max_results is not None:
        return message_ids[:max_results]
    return message_ids


def delete_message_batch(service, message_ids, batch_size=100):
    """Delete a list of Gmail message IDs in batches to avoid large API payloads."""
    if not message_ids:
        return {"deleted_count": 0, "failed_count": 0, "failed": []}

    deleted = []
    failed = []

    for start in range(0, len(message_ids), batch_size):
        batch = message_ids[start:start + batch_size]
        try:
            service.users().messages().batchDelete(userId="me", body={"ids": batch}).execute()
            deleted.extend(batch)
        except HttpError as err:
            if "insufficientPermissions" in str(err):
                raise PermissionError(
                    "Gmail permissions are missing. Delete token.json and re-run the app to "
                    "re-authorize with the Gmail Desktop OAuth scope."
                ) from err

            for msg_id in batch:
                try:
                    service.users().messages().delete(userId="me", id=msg_id).execute()
                    deleted.append(msg_id)
                except HttpError as inner_err:
                    failed.append({"id": msg_id, "error": str(inner_err)})

    return {"deleted_count": len(deleted), "failed_count": len(failed), "failed": failed}


def trash_unread_spam_messages(service, message_ids=None):
    """Move unread and spam messages to Trash. Fetches unread and spam IDs if none are provided."""
    if message_ids is None:
        # Add the lists together
        # unread_list = search_unread(service)
        unread_list = search_unread(service)
        spam_list = search_spam(service)
        message_ids = unread_list + spam_list


    if not message_ids:
        return {"trashed_count": 0, "failed_count": 0, "failed": [], "status": "No unread messages to trash."}
    else:
        trashed, failed = [], []
        for msg_id in message_ids:
            try:
                service.users().messages().trash(userId="me", id=msg_id).execute()
                trashed.append(msg_id)
            except HttpError as err:
                failed.append({"id": msg_id, "error": str(err)})
        return {"trashed_count": len(trashed), "failed_count": len(failed), "failed": failed}


def empty_trash(service, batch_size=100):
    """Permanently delete every message currently in Trash in safe batches."""
    message_ids = list_message_ids(service, label_ids=["TRASH"])
    if not message_ids:
        return {"deleted_count": 0, "failed_count": 0, "failed": [], "status": "Trash is already empty."}

    return delete_message_batch(service, message_ids, batch_size=batch_size)

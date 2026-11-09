"""GMX Mail client using IMAP for email cleanup and trash management."""
import imaplib
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ModuleNotFoundError:
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))

IMAP_SERVER = "imap.gmx.com"
PORT = 993


def get_gmx_credentials():
    """Retrieve GMX email address and app password from environment variables."""
    email_address = os.getenv("GMX_EMAIL") or os.getenv("GMX_EMAIL_ADDRESS")
    app_password = os.getenv("GMX_APP_PASSWORD") or os.getenv("GMX_PASSWORD")
    if not email_address or not app_password:
        raise ValueError(
            "GMX credentials missing. Please set GMX_EMAIL and GMX_APP_PASSWORD in your .env file."
        )
    return email_address, app_password


def get_imap_connection():
    """Establish an authenticated IMAP SSL connection to GMX."""
    email_address, app_password = get_gmx_credentials()
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, PORT)
    mail.login(email_address, app_password)
    return mail


def _parse_mailbox_list(mail):
    """Parse IMAP LIST response into dictionaries with flags, delimiter, and clean name."""
    status, folder_list = mail.list()
    if status != "OK" or not folder_list:
        return []

    mailboxes = []
    pattern = re.compile(r'^\((?P<flags>[^)]*)\)\s+(?P<delim>"[^"]+"|None|\S+)\s+(?P<name>.*)$')
    for item in folder_list:
        decoded = item.decode("utf-8", errors="replace") if isinstance(item, bytes) else str(item)
        match = pattern.match(decoded.strip())
        if match:
            flags = [f.strip().lower() for f in match.group("flags").split() if f.strip()]
            name = match.group("name").strip()
            if name.startswith('"') and name.endswith('"') and len(name) >= 2:
                name = name[1:-1]
            mailboxes.append({
                "flags": flags,
                "delim": match.group("delim").strip('"'),
                "name": name,
            })
    return mailboxes


def _find_folder_by_role_or_aliases(mail, role_flag, aliases, default_name):
    """Locate mailbox by RFC 6154 special-use flag, exact alias match, or substring."""
    mailboxes = _parse_mailbox_list(mail)

    # 1. Match special-use attributes (e.g. \trash, \junk)
    for mb in mailboxes:
        if role_flag.lower() in mb["flags"]:
            return mb["name"]

    # 2. Match exact alias
    lower_aliases = [a.lower() for a in aliases]
    for mb in mailboxes:
        if mb["name"].lower() in lower_aliases:
            return mb["name"]

    # 3. Match substring
    for mb in mailboxes:
        for alias in lower_aliases:
            if alias in mb["name"].lower():
                return mb["name"]

    return default_name


def _find_trash_folder(mail):
    """Detect GMX's Trash folder name across different language settings."""
    return _find_folder_by_role_or_aliases(
        mail,
        r"\trash",
        ["trash", "papierkorb", "gelöschte elemente", "gel&apy-schte elemente", "deleted"],
        "Trash",
    )


def _find_spam_folder(mail):
    """Detect GMX's Spam folder name across different language settings."""
    return _find_folder_by_role_or_aliases(
        mail,
        r"\junk",
        ["spam", "junk", "spamverdacht", "junk mail", "spam mail"],
        "Spam",
    )


def _select_folder(mail, folder_name):
    """Attempt to select a folder trying various quoting or path candidates."""
    if not folder_name:
        return None, None
    cleaned = folder_name.strip().strip('"')
    candidates = [
        folder_name,
        cleaned,
        f'"{cleaned}"',
        f"INBOX/{cleaned}",
    ]
    for candidate in candidates:
        try:
            status, data = mail.select(candidate)
            if status == "OK":
                return candidate, data
        except Exception:
            continue
    return None, None


def _copy_batch(mail, id_set, folder_name):
    """Copy a sequence set of message IDs to target folder, trying quoted variants if needed."""
    cleaned = (folder_name or "").strip().strip('"')
    candidates = [cleaned, f'"{cleaned}"']
    for target in candidates:
        try:
            status, _ = mail.copy(id_set, target)
            if status == "OK":
                return True
        except Exception:
            continue
    return False


def _move_messages_to_trash(mail, source_folder_name, search_criteria, trash_folder_name):
    """Move all matching messages from a source folder to Trash in fast batches."""
    if not source_folder_name:
        return 0

    selected, _ = _select_folder(mail, source_folder_name)
    if not selected:
        print(f"[GMX] Could not select source folder '{source_folder_name}'", flush=True)
        return 0

    status, response = mail.search(None, search_criteria)
    if status != "OK" or not response or not response[0]:
        return 0

    msg_ids = response[0].split()
    total = len(msg_ids)
    if total == 0:
        return 0

    print(f"[GMX] Found {total} message(s) in '{selected}'. Moving to '{trash_folder_name}'...", flush=True)

    moved = 0
    for i in range(0, total, 100):
        batch = msg_ids[i : i + 100]
        id_set = b",".join(batch)
        if _copy_batch(mail, id_set, trash_folder_name):
            mail.store(id_set, "+FLAGS", "(\\Deleted)")
            moved += len(batch)
        else:
            for msg_id in batch:
                if _copy_batch(mail, msg_id, trash_folder_name):
                    mail.store(msg_id, "+FLAGS", "(\\Deleted)")
                    moved += 1

    try:
        mail.expunge()
    except Exception:
        pass

    print(f"[GMX] Moved {moved} message(s) from '{selected}' to '{trash_folder_name}'.", flush=True)
    return moved


def trash_unread_messages():
    """Move unread GMX inbox messages and spam messages to the Trash folder."""
    mail = get_imap_connection()
    try:
        trash_folder = _find_trash_folder(mail)
        print(f"[GMX] Detected Trash folder: '{trash_folder}'", flush=True)

        unread_count = _move_messages_to_trash(mail, "INBOX", "UNSEEN", trash_folder)

        spam_folder = _find_spam_folder(mail)
        print(f"[GMX] Detected Spam folder: '{spam_folder}'", flush=True)
        spam_count = _move_messages_to_trash(mail, spam_folder, "ALL", trash_folder)

        total_moved = unread_count + spam_count
        return {
            "deleted_count": total_moved,
            "status": f"Moved {unread_count} unread inbox and {spam_count} spam messages to Trash.",
        }
    finally:
        try:
            mail.close()
        except Exception:
            pass
        try:
            mail.logout()
        except Exception:
            pass


trash_unread_spam_messages = trash_unread_messages


def trash_spam_messages():
    """Move all messages in GMX's Spam folder to the Trash folder."""
    mail = get_imap_connection()
    try:
        trash_folder = _find_trash_folder(mail)
        spam_folder = _find_spam_folder(mail)
        deleted_count = _move_messages_to_trash(mail, spam_folder, "ALL", trash_folder)

        return {
            "deleted_count": deleted_count,
            "status": f"Moved {deleted_count} spam messages to Trash.",
        }
    finally:
        try:
            mail.close()
        except Exception:
            pass
        try:
            mail.logout()
        except Exception:
            pass


def debug_gmx_mailboxes():
    """Print the exact mailbox names GMX exposes so the correct Spam/Trash folder can be selected."""
    mail = get_imap_connection()
    try:
        mailboxes = _parse_mailbox_list(mail)
        for mb in mailboxes:
            print(f"Name: {mb['name']} | Flags: {mb['flags']} | Delim: {mb['delim']}", flush=True)
        return mailboxes
    finally:
        try:
            mail.close()
        except Exception:
            pass
        try:
            mail.logout()
        except Exception:
            pass


def count_messages_in_folder(folder_name):
    """Return the number of messages in a specific GMX folder."""
    mail = get_imap_connection()
    try:
        selected, _ = _select_folder(mail, folder_name)
        if not selected:
            return 0
        status, response = mail.search(None, "ALL")
        if status == "OK" and response and response[0]:
            return len(response[0].split())
        return 0
    finally:
        try:
            mail.close()
        except Exception:
            pass
        try:
            mail.logout()
        except Exception:
            pass


def empty_trash():
    """Permanently purge all messages from GMX's Trash folder."""
    mail = get_imap_connection()
    try:
        trash_folder = _find_trash_folder(mail)
        selected, _ = _select_folder(mail, trash_folder)
        if not selected:
            return {"deleted_count": 0, "status": f"Could not access GMX Trash folder ('{trash_folder}')."}

        print(f"[GMX] Emptying Trash folder '{selected}'...", flush=True)
        status, response = mail.search(None, "ALL")
        if status != "OK" or not response or not response[0]:
            return {"deleted_count": 0, "status": "GMX Trash is already empty."}

        msg_ids = response[0].split()
        total = len(msg_ids)
        if total == 0:
            return {"deleted_count": 0, "status": "GMX Trash is already empty."}

        print(f"[GMX] Found {total} message(s) in Trash to purge.", flush=True)
        deleted_count = 0
        for i in range(0, total, 100):
            batch = msg_ids[i : i + 100]
            id_set = b",".join(batch)
            res, _ = mail.store(id_set, "+FLAGS", "(\\Deleted)")
            if res == "OK":
                deleted_count += len(batch)
            else:
                for msg_id in batch:
                    r, _ = mail.store(msg_id, "+FLAGS", "(\\Deleted)")
                    if r == "OK":
                        deleted_count += 1

        mail.expunge()
        print(f"[GMX] Expunged {deleted_count} message(s) permanently from Trash.", flush=True)
        return {
            "deleted_count": deleted_count,
            "status": f"GMX Trash emptied successfully ({deleted_count} messages deleted).",
        }
    finally:
        try:
            mail.close()
        except Exception:
            pass
        try:
            mail.logout()
        except Exception:
            pass


if __name__ == "__main__":
    debug_gmx_mailboxes()
    print("Spam count:", count_messages_in_folder(_find_spam_folder(get_imap_connection())))
    print("Trash count:", count_messages_in_folder(_find_trash_folder(get_imap_connection())))
    print(trash_unread_messages()["status"])
# Gmail Cleanup App

Deletes unread Gmail messages and empties Trash using Google Desktop OAuth only.

## Setup

1. **Create a Google Cloud OAuth client**
   - Go to Google Cloud Console → APIs & Services → Enable "Gmail API".
   - Create OAuth client credentials of type "Desktop app".
   - Download the JSON file, save it as `credentials.json` in this folder.
   - No redirect URL is required for a Desktop app; Google uses a local localhost callback automatically.

2. **Install dependencies**

   ```
   pip install -r requirements.txt
   ```

3. **Run the desktop app**

   ```
   python desktop_app.py
   ```

   The first run opens a browser to complete Gmail OAuth consent in the desktop flow; a `token.json` is cached locally afterward.

4. **Run the terminal cleanup script**
   ```
   python main.py
   ```
   This version connects to Gmail and immediately deletes unread mail, then empties Trash.

## Notes

- Uses the full `https://mail.google.com/` scope because permanently deleting Trash requires it. `credentials.json` and `token.json` are gitignored — keep them private.
- Trashing is a soft delete (recoverable for 30 days); `empty_trash()` permanently deletes messages already in Trash and cannot be undone.

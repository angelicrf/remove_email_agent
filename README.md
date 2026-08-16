# Gmail Agent Desktop App

A desktop application with an AI-powered agent to manage your Gmail account. Perform tasks like cleaning your inbox, summarizing recent emails, or sending messages using natural language commands.

## Setup

Follow these steps to get the application running.

### 1. Google Cloud OAuth Credentials

The application needs permission to access your Gmail account.

- Go to the Google Cloud Console.
- Create a new project or select an existing one.
- Go to **APIs & Services → Library** and enable the **Gmail API**.
- Go to **APIs & Services → Credentials**.
- Click **Create Credentials → OAuth client ID**.
- Select **Desktop app** as the application type.
- Download the JSON file and save it as `credentials.json` in the project's root directory.

### 2. OpenAI API Key

The AI agent uses OpenAI's models to understand your commands.

- Create an API key in your OpenAI Dashboard.
- In the project's root directory, create a file named `.env`.
- Add your API key to the `.env` file like this:
  ```
  OPENAI_API_KEY="your_key_here"
  ```

### 3. Install Dependencies

```
pip install -r requirements.txt
```

## Usage

### Desktop App (with AI Agent)

This is the main interface for interacting with your Gmail.

```
python desktop_app.py
```

1.  **Connect to Gmail**: Click the "Connect Gmail" button. This will open a browser window for you to grant the application permission. A `token.json` file will be created to keep you logged in.
2.  **Manual Cleanup**: Use the "Clean unread" and "Empty trash" buttons for quick, predefined actions.
3.  **AI Agent**: Type a command into the text box and click "Run Agent".
    - `"Summarize my last 5 emails"`
    - `"Send an email to john.doe@example.com with the subject 'Meeting' and body 'Are we still on for tomorrow?'"`
    - `"Clean up my unread mail"`

### Terminal Cleanup Script

For a quick, non-interactive cleanup that trashes unread/spam emails and empties the trash.

```
python main.py
```

## Notes

- **Privacy**: The `credentials.json`, `token.json`, and `.env` files contain sensitive information. They are included in `.gitignore` and should never be shared or committed to version control.
- **Permissions**: The app requests broad permissions (`gmail.modify`, `gmail.send`) to perform its tasks. Review the scopes during the OAuth consent process.
- **Deletion**: Trashing messages is a soft delete (recoverable from the Trash folder for 30 days). Emptying the trash is a permanent action and cannot be undone.

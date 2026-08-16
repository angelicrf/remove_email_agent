"""Desktop GUI for Gmail cleanup using Google OAuth desktop flow."""
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import agent
import gmail_client


class GmailCleanupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gmail Cleanup Agent")
        self.root.geometry("520x300")
        self.root.minsize(480, 260)

        self.service = None

        self.status_var = tk.StringVar(value="Not connected")
        self.result_var = tk.StringVar(value="")

        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Gmail cleanup", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Manual cleanup or use the AI agent for tasks.").pack(anchor="w", pady=(4, 12))

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", pady=(0, 12))

        ttk.Button(button_row, text="Connect Gmail", command=self.connect_gmail).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Clean unread", command=self.clean_unread).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Empty trash", command=self.empty_trash).pack(side="left")

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(frame, text="AI Agent", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.agent_instruction = tk.StringVar(value="Clean up my unread mail")
        ttk.Entry(frame, textvariable=self.agent_instruction).pack(fill="x", pady=(4, 8))

        agent_button_row = ttk.Frame(frame)
        agent_button_row.pack(fill="x", pady=(0, 12))
        ttk.Button(agent_button_row, text="Run Agent", command=self.run_agent).pack(side="left")

        ttk.Label(frame, textvariable=self.status_var, foreground="#1f6feb").pack(anchor="w")

        output = ttk.Label(frame, textvariable=self.result_var, wraplength=460, justify="left")
        output.pack(anchor="w", pady=(12, 0))

    def connect_gmail(self):
        def task():
            try:
                self.service = gmail_client.get_gmail_service()
                self.status_var.set("Connected to Gmail")
                self.result_var.set("OAuth completed successfully.")
            except Exception as exc:  # pragma: no cover - UI feedback path
                self.status_var.set("Connection failed")
                self.result_var.set(str(exc))
                messagebox.showerror("Authentication failed", str(exc))

        threading.Thread(target=task, daemon=True).start()

    def clean_unread(self):
        if self.service is None:
            messagebox.showwarning("Not connected", "Connect to Gmail first.")
            return

        def task():
            try:
                result = gmail_client.trash_unread_spam_messages(self.service)
                self.status_var.set(f"Moved {result['trashed_count']} unread emails to Trash")
                self.result_var.set(
                    f"Moved: {result['trashed_count']}. Failed: {result['failed_count']}."
                )
            except Exception as exc:  # pragma: no cover - UI feedback path
                self.status_var.set("Cleanup failed")
                self.result_var.set(str(exc))
                messagebox.showerror("Cleanup failed", str(exc))

        threading.Thread(target=task, daemon=True).start()

    def empty_trash(self):
        if self.service is None:
            messagebox.showwarning("Not connected", "Connect to Gmail first.")
            return

        def task():
            try:
                result = gmail_client.empty_trash(self.service)
                self.status_var.set(f"Deleted {result['deleted_count']} messages from Trash")
                self.result_var.set(
                    f"Permanent delete complete. Deleted: {result['deleted_count']}. "
                    f"Failed: {result['failed_count']}."
                )
            except Exception as exc:  # pragma: no cover - UI feedback path
                self.status_var.set("Trash cleanup failed")
                self.result_var.set(str(exc))
                messagebox.showerror("Trash cleanup failed", str(exc))

        threading.Thread(target=task, daemon=True).start()

    def run_agent(self):
        if self.service is None:
            messagebox.showwarning("Not connected", "Connect to Gmail first.")
            return

        instruction = self.agent_instruction.get()
        if not instruction:
            messagebox.showwarning("Input required", "Please enter an instruction for the agent.")
            return

        def task():
            try:
                self.status_var.set(f"Agent running with instruction: '{instruction}'...")
                self.result_var.set("Please wait...")
                result = agent.run_agent(instruction)
                self.status_var.set("Agent finished.")
                self.result_var.set(result)
            except Exception as exc:
                self.status_var.set("Agent failed")
                self.result_var.set(str(exc))
                messagebox.showerror("Agent failed", str(exc))

        threading.Thread(target=task, daemon=True).start()


def main():
    root = tk.Tk()
    GmailCleanupApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

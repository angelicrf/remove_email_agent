"""
PyInstaller build script for the Gmail Agent Desktop App.

This script packages the application into a single executable file,
including the necessary data files and a custom icon.

To run this script:
1. Make sure PyInstaller is installed: pip install pyinstaller
2. Place an icon file named 'app.ico' in the project root.
3. Run from the terminal: python build.py

The final executable will be located in the 'dist' folder.
"""
import PyInstaller.__main__

if __name__ == "__main__":
    # These are the files that need to be accessible by the app at runtime.
    # PyInstaller will place them in the same directory as the executable.
    data_files = [
        "credentials.json",
        ".env",
    ]

    PyInstaller.__main__.run([
        "desktop_app.py",
        "--name=GmailAgent",
        "--onefile",
        "--windowed",
        "--icon=app.ico",
        "--hidden-import=dotenv",
        "--collect-all=dotenv",
    ] + [f"--add-data={f};." for f in data_files])
# 🎬 YouTube Downloader UI Pro+

A simple web interface built with Streamlit to download YouTube videos in various formats and qualities. This tool utilizes `pytubefix` and `yt-dlp` for fetching video information and downloading streams, and `ffmpeg` for merging separate video and audio streams for the best quality downloads.

## 🚀 Try it Online!

You can try a live version of this application hosted on Streamlit Community Cloud:

**[➡️ Launch App: https://youtube-downloader-ui.streamlit.app/](https://youtube-downloader-ui.streamlit.app/)**

*(Note: The online version runs on shared resources and might have limitations compared to running locally, especially for very long or large files.)*

## ✨ Features

*   **Easy URL Input:** Paste any standard YouTube video or shorts URL.
*   **Fetch Video Info:** Displays the video title upon fetching.
*   **Multiple Download Modes:**
    *   **✨ Best Quality (DASH Auto):** Automatically selects the highest resolution video and best quality non-Opus audio stream, downloads them separately, and merges them using FFmpeg (Requires FFmpeg).
    *   **⚙️ Manual Quality (DASH Manual):** Allows manual selection of specific video and audio streams (adaptive DASH formats) for download and merging (Requires FFmpeg).
    *   **🚀 Progressive (Simple):** Downloads a single file containing both video and audio (typically up to 720p, no FFmpeg needed).
*   **Download Progress:** Real-time progress bar, download speed, and ETA estimation.
*   **Error Handling:** Provides feedback for invalid URLs, unavailable videos, or download/merge errors.
*   **Filename Sanitization:** Creates safe filenames based on the video title.
*   **FFmpeg Check:** Warns the user if FFmpeg is not detected in the system PATH when required modes are selected.
*   **Dev Container Support:** Includes configuration for easy setup using VS Code Dev Containers or GitHub Codespaces.

## 🛠 Prerequisites

### Local Setup

*   **Python:** Version 3.11+ recommended (as specified in `devcontainer.json`).
*   **pip:** Python package installer (usually comes with Python).
*   **FFmpeg:** **Required** for the "Best Quality" and "Manual Quality" download options which involve merging separate video and audio files.
    *   Download and install from [ffmpeg.org](https://ffmpeg.org/download.html).
    *   Ensure `ffmpeg` is added to your system's PATH environment variable.

### Dev Container / Codespaces

*   **Docker:** If using VS Code Dev Containers locally.
*   **VS Code Extension:** [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension if using VS Code locally.
*   Or, simply use **GitHub Codespaces**.

## ⚙️ Setup and Installation

### 1. Local Environment

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/your-repo-name.git # Replace with actual repo URL
    cd your-repo-name
    ```
2.  **Install FFmpeg:** Follow the instructions on the [FFmpeg website](https://ffmpeg.org/download.html) for your operating system and ensure it's in your PATH. You can verify by running `ffmpeg -version` in your terminal.
    *(On Debian/Ubuntu systems, you might install it via `sudo apt update && sudo apt install ffmpeg`)*

3.  **(Optional but Recommended) Create a Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate # On Windows use `venv\Scripts\activate`
    ```

4.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### 2. Using Dev Container / GitHub Codespaces

This is the recommended way for a hassle-free setup, especially if you don't want to install FFmpeg manually.

1.  **Open in Codespaces:** Click the "Code" button on the GitHub repository page and select "Open with Codespaces".
2.  **Open in VS Code Dev Container:**
    *   Make sure Docker Desktop is running.
    *   Open the cloned repository folder in VS Code.
    *   VS Code should automatically detect the `.devcontainer/devcontainer.json` file and ask if you want to "Reopen in Container". Click yes.

The Dev Container setup will automatically:
*   Use the specified Python 3.11 Docker image.
*   Install `ffmpeg` (from `packages.txt`).
*   Install all Python requirements (from `requirements.txt`).
*   Install recommended VS Code extensions (`ms-python.python`, `ms-python.vscode-pylance`).
*   Start the Streamlit application automatically after the container is ready.
*   Forward the necessary port (8501) for you to access the web UI.

## ▶️ Usage

1.  **Run the Streamlit app (if running locally):**
    ```bash
    streamlit run youtube-download-ui.py
    ```
2.  **Access the UI:** Open your web browser and navigate to `http://localhost:8501` (or the URL provided by Codespaces/Dev Containers).
3.  **Paste URL:** Enter the YouTube video URL into the text input field.
4.  **Fetch Info:** Click the "Fetch Video Info" button.
5.  **Choose Option:** Select your preferred download mode (Best Quality, Manual, or Progressive). Configure quality if using Manual mode.
6.  **Download:** Click the corresponding download button.
7.  **Save:** Once the download (and merge, if applicable) is complete, a "Save Video to Your Device" button will appear. Click it to save the file.

## 📦 Dependencies

### System

*   `ffmpeg` (Required for DASH stream merging)

### Python

Listed in `requirements.txt`:

*   `streamlit`: For creating the web UI.
*   `yt-dlp`: A fork of youtube-dl, used internally by pytubefix for some operations.
*   `pytubefix`: Library for interacting with YouTube and downloading streams.

## ⚠️ Disclaimer

Please be aware of and respect copyright laws and YouTube's Terms of Service when downloading videos. This tool is intended for personal, offline viewing of publicly available content where permitted. The developers assume no responsibility for misuse.
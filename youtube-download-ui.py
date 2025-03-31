import streamlit as st
import yt_dlp
import sys
import os
import re
# We don't need subprocess or shutil for the final version anymore
# import subprocess
# import shutil

# --- Page Config (MUST BE THE FIRST STREAMLIT COMMAND) ---
st.set_page_config(page_title="YouTube Downloader", layout="centered")

# --- Configuration ---
OUTPUT_DIR = "downloads"
if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

# --- FFmpeg Check Removed ---
# We are removing the initial check as the subprocess tests confirmed
# ffmpeg is available and executable in the Streamlit environment.
# yt-dlp itself should find it during the download process.
# ffmpeg_found = True # Assuming it will be found based on successful tests

# --- Streamlit UI ---
st.title("🎬 YouTube Video Downloader (MP4)")
st.caption("Download specific video qualities as MP4 files (requires FFmpeg for best results)")
# Add a small note confirming FFmpeg seems okay based on tests (optional)
# st.caption("Note: Direct execution tests indicate FFmpeg is accessible.")

# --- Session State Initialization ---
if 'video_info' not in st.session_state: st.session_state.video_info = None
if 'download_status' not in st.session_state: st.session_state.download_status = None
if 'progress' not in st.session_state: st.session_state.progress = 0
if 'status_message' not in st.session_state: st.session_state.status_message = ""
if 'final_filename' not in st.session_state: st.session_state.final_filename = None
if 'error_message' not in st.session_state: st.session_state.error_message = None
if 'status_text_success' not in st.session_state: st.session_state.status_text_success = False
if 'status_text_error' not in st.session_state: st.session_state.status_text_error = False

# --- Input URL ---
url = st.text_input("Enter YouTube Video URL:", key="video_url")

# --- Fetch Video Info Button ---
if st.button("Fetch Video Info", disabled=not url):
    st.session_state.video_info = None; st.session_state.download_status = 'fetching'
    st.session_state.final_filename = None; st.session_state.error_message = None
    st.session_state.progress = 0; st.session_state.status_message = ""
    st.session_state.status_text_success = False; st.session_state.status_text_error = False
    if url:
        with st.spinner("Fetching video information..."):
            try:
                ydl_opts_info = { 'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True }
                with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                    info_dict = ydl.extract_info(url, download=False)
                    video_title = info_dict.get('title', 'Unknown Title'); formats = info_dict.get('formats', [])
                available_qualities = {}
                for f in formats:
                    if f.get('vcodec') != 'none' and f.get('height') is not None and f.get('acodec') == 'none':
                        height = f.get('height'); fps = f.get('fps'); tbr = f.get('tbr')
                        label = f"{height}p" + (f"{int(round(fps))}" if fps and fps > 30 else "")
                        quality_key = (height, fps if fps else 0, tbr if tbr else 0)
                        if label not in available_qualities or quality_key > available_qualities[label]['key']:
                             available_qualities[label] = {'label': label, 'height': height, 'fps': fps, 'format_id': f['format_id'], 'key': quality_key}
                if not available_qualities:
                    st.session_state.error_message = "Error: No suitable video-only formats found for merging."; st.session_state.download_status = 'error'
                else:
                    sorted_qualities = sorted(available_qualities.values(), key=lambda item: item['key'], reverse=True)
                    st.session_state.video_info = {'title': video_title, 'qualities': sorted_qualities, 'url': url}; st.session_state.download_status = 'selecting'
            except yt_dlp.utils.DownloadError as e: st.session_state.error_message = f"Error processing URL: {e}"; st.session_state.download_status = 'error'
            except Exception as e: st.session_state.error_message = f"An unexpected error occurred during info fetch: {e}"; st.session_state.download_status = 'error'
    else: st.warning("Please enter a valid YouTube URL."); st.session_state.download_status = None


# --- Display Video Info and Quality Selection ---
if st.session_state.download_status == 'error' and st.session_state.error_message:
    if not st.session_state.get("status_text_error", False): st.error(st.session_state.error_message); st.session_state.status_text_error = True

if st.session_state.download_status == 'selecting' and st.session_state.video_info:
    info = st.session_state.video_info; st.subheader(f"Video Found: {info['title']}")
    quality_options = [q['label'] for q in info['qualities']]
    if not quality_options:
         st.warning("No downloadable video qualities detected."); st.session_state.download_status = 'error'
         st.session_state.error_message = "Could not find any video quality options."
         if not st.session_state.get("status_text_error", False): st.error(st.session_state.error_message); st.session_state.status_text_error = True
    else:
        selected_quality_label = st.radio("Select Video Quality:", options=quality_options, index=0, key="quality_choice")
        chosen_quality_info = next((q for q in info['qualities'] if q['label'] == selected_quality_label), None)

        # --- Download Button ---
        if chosen_quality_info and st.button("Download Selected Quality", key="download_button"):
            # No warning needed here now based on successful tests
            # if not ffmpeg_found: st.warning(...)

            st.session_state.download_status = 'downloading'; st.session_state.progress = 0
            st.session_state.status_message = "Starting download..."; st.session_state.final_filename = None
            st.session_state.error_message = None; st.session_state.status_text_success = False; st.session_state.status_text_error = False
            progress_bar = st.progress(0); status_text = st.empty()

            def hook(d):
                # (Hook logic remains the same)
                if d['status'] == 'downloading':
                    percent_str = d.get('_percent_str', '0%'); percent_clean = re.sub(r'\x1b\[[0-9;]*m', '', percent_str).replace('%','').strip()
                    try: progress_value = max(0.0, min(1.0, float(percent_clean) / 100.0))
                    except ValueError: progress_value = st.session_state.progress
                    speed = d.get('_speed_str', 'N/A').strip(); eta = d.get('_eta_str', 'N/A').strip()
                    st.session_state.progress = progress_value; st.session_state.status_message = f"Downloading: {percent_str} at {speed}, ETA: {eta}"
                    try:
                        if st.session_state.download_status == 'downloading': progress_bar.progress(progress_value); status_text.info(st.session_state.status_message)
                    except Exception as ui_update_error: print(f"Debug: Error updating UI in hook: {ui_update_error}")
                elif d['status'] == 'finished':
                    component_filename = d.get('filename') or d.get('info_dict', {}).get('filepath', 'component')
                    st.session_state.status_message = f"Processing: {os.path.basename(component_filename)}. Waiting for final conversion..."
                    try:
                        if st.session_state.download_status == 'downloading': status_text.info(st.session_state.status_message); progress_bar.progress(1.0)
                    except Exception as ui_update_error: print(f"Debug: Error updating UI in hook (finished): {ui_update_error}")
                elif d['status'] == 'error':
                     st.session_state.download_status = 'error'; st.session_state.error_message = "yt-dlp reported an error during download/processing."
                     try:
                        if not st.session_state.get("status_text_error", False): status_text.error(st.session_state.error_message); progress_bar.progress(1.0); st.session_state.status_text_error = True
                     except Exception as ui_update_error: print(f"Debug: Error updating UI in hook (error): {ui_update_error}")

            # --- Prepare Download Options ---
            format_selector = f"{chosen_quality_info['format_id']}+bestaudio/best"
            safe_title = re.sub(r'[\\/*?:"<>|]', "", info['title'])[:100]; quality_tag = chosen_quality_info['label']
            base_output_name = f'{safe_title} [{quality_tag}]'
            output_template = os.path.join(OUTPUT_DIR, f'{base_output_name}.%(ext)s')
            final_expected_path = os.path.join(OUTPUT_DIR, f'{base_output_name}.mp4')

            ydl_opts_download = {
                'format': format_selector, 'outtmpl': output_template, 'progress_hooks': [hook],
                'noplaylist': True, 'merge_output_format': 'mp4',
                'postprocessors': [{'key': 'FFmpegVideoConvertor','preferedformat': 'mp4'},
                                   {'key': 'FFmpegMetadata','add_metadata': True},
                                   {'key': 'FFmpegEmbedSubtitle'}],
                 'quiet': True, 'no_warnings': True, 'verbose': False, 'ignoreerrors': False, 'fixup': 'warn',
                 # Ensure 'ffmpeg_location' is NOT set, so yt-dlp uses PATH
            }

            # --- Execute Download ---
            try:
                with st.spinner(f"Downloading and converting '{info['title']}' ({quality_tag})... Please wait."):
                    status_text.info("Initiating download with yt-dlp...")
                    # yt-dlp should find ffmpeg using PATH here
                    with yt_dlp.YoutubeDL(ydl_opts_download) as ydl: ydl.download([info['url']])
                if os.path.exists(final_expected_path):
                    st.session_state.download_status = 'finished'; st.session_state.final_filename = final_expected_path
                    st.session_state.status_message = f"Download successful: {os.path.basename(final_expected_path)}"
                    status_text.success(st.session_state.status_message); progress_bar.progress(1.0); st.session_state.status_text_success = True
                else: # Handle case where download finishes but expected file is missing
                    st.session_state.download_status = 'error'; st.session_state.final_filename = None; found_other_file = None
                    try:
                        for f in os.listdir(OUTPUT_DIR):
                            if f.startswith(base_output_name): found_other_file = f; break
                    except OSError: pass
                    if found_other_file: st.session_state.error_message = f"Download finished, but the final file seems to be '{found_other_file}' instead of the expected MP4. FFmpeg might have had issues during conversion."
                    else: st.session_state.error_message = "Download process finished, but the final MP4 file could not be found. Check console logs or permissions."
                    if not st.session_state.get("status_text_error", False): status_text.error(st.session_state.error_message); progress_bar.progress(1.0); st.session_state.status_text_error = True
            except yt_dlp.utils.DownloadError as e:
                st.session_state.download_status = 'error'; err_str = str(e).lower()
                # Check if error message hints at FFmpeg issues during the actual process
                if "ffmpeg" in err_str or "post-process" in err_str or "merge" in err_str or "muxing" in err_str or "convert" in err_str:
                    st.session_state.error_message = f"Download/Conversion Error (FFmpeg issue likely during process): {e}\nCheck console for details."
                else: st.session_state.error_message = f"yt-dlp Download Error: {e}"
                if not st.session_state.get("status_text_error", False):
                    try: status_text.error(st.session_state.error_message); progress_bar.progress(1.0)
                    except Exception: pass; st.session_state.status_text_error = True
            except Exception as e: # Catch any other unexpected errors
                st.session_state.download_status = 'error'; st.session_state.error_message = f"An unexpected error occurred during download/processing: {e}"
                if not st.session_state.get("status_text_error", False):
                    try: status_text.error(st.session_state.error_message); progress_bar.progress(1.0)
                    except Exception: pass; st.session_state.status_text_error = True

# --- Display Download Button ---
if st.session_state.download_status == 'finished' and st.session_state.final_filename:
    try:
        if not st.session_state.get("status_text_success", False): st.success(st.session_state.status_message); st.session_state.status_text_success = True
        with open(st.session_state.final_filename, "rb") as fp:
            btn = st.download_button(label="Download MP4 File", data=fp, file_name=os.path.basename(st.session_state.final_filename), mime="video/mp4", key="download_final_button")
    except FileNotFoundError:
        if not st.session_state.get("status_text_error", False): st.error(f"Error: The downloaded file '{st.session_state.final_filename}' was not found."); st.session_state.download_status = 'error'; st.session_state.status_text_error = True
    except Exception as e:
        if not st.session_state.get("status_text_error", False): st.error(f"Error reading file for download button: {e}"); st.session_state.download_status = 'error'; st.session_state.status_text_error = True

# --- Display Final Error Message ---
elif st.session_state.download_status == 'error' and st.session_state.error_message:
    if not st.session_state.get("status_text_error", False): st.error(f"Failed: {st.session_state.error_message}"); st.session_state.status_text_error = True

# --- Footer ---
st.markdown("---")
st.caption("Built with Streamlit & yt-dlp")
# No FFmpeg warning needed in footer now
# if not ffmpeg_found: st.caption(...)
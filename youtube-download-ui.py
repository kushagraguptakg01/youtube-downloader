import streamlit as st
import yt_dlp
import sys
import os
import re # For URL validation and progress string cleaning
import traceback # To print detailed error information

# --- Page Config (MUST BE THE FIRST STREAMLIT COMMAND) ---
st.set_page_config(page_title="YouTube Downloader", layout="centered")

# --- Configuration ---
OUTPUT_DIR = "downloads"
if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

# --- Helper Function: YouTube URL Validation ---
@st.cache_data # Cache the regex compilation
def compile_youtube_regex():
    pattern = re.compile(
        r'^(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})'
    )
    return pattern

YOUTUBE_REGEX = compile_youtube_regex()

def is_valid_youtube_url(url):
    """Checks if the URL matches common YouTube video patterns."""
    if not url:
        return False
    return YOUTUBE_REGEX.match(url) is not None

# --- Streamlit UI ---
st.title("🎬 YouTube Video Downloader (Compatible MP4)")
st.caption("Enter a YouTube video URL, fetch available qualities, and download as a widely compatible MP4 (H.264/AAC).")
st.info("ℹ️ Downloads are re-encoded for better compatibility, which may take longer. Requires FFmpeg.")


# --- Session State Initialization ---
defaults = {
    'video_info': None, 'download_status': None, 'progress': 0.0,
    'status_message': "", 'final_filename': None, 'error_message': None,
    'status_text_success': False, 'status_text_error': False,
    'current_url': "", 'last_fetched_url': None,
    'progress_bar_text': "" # Add state for progress bar text
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- URL Input Form ---
with st.form("url_form"):
    url_input = st.text_input(
        "YouTube Video URL:",
        value=st.session_state.current_url,
        key="video_url_input",
        placeholder="e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    submitted = st.form_submit_button("Fetch Video Info")

    if submitted:
        st.session_state.current_url = url_input
        # Reset states for new fetch attempt
        st.session_state.video_info = None
        st.session_state.download_status = None
        st.session_state.final_filename = None
        st.session_state.error_message = None
        st.session_state.status_text_success = False
        st.session_state.status_text_error = False
        st.session_state.progress = 0.0
        st.session_state.progress_bar_text = "" # Reset progress text

        if is_valid_youtube_url(url_input):
            if url_input != st.session_state.last_fetched_url:
                st.session_state.download_status = 'fetching'
            else:
                # If URL is the same, go back to selection if info exists
                st.session_state.download_status = 'selecting' if st.session_state.video_info else 'fetching'
        else:
            st.error("Invalid YouTube URL format. Please enter a valid link.")
            st.session_state.download_status = 'error'
            st.session_state.error_message = "Invalid URL format entered."
            st.session_state.status_text_error = True # Flag to prevent duplicate msg

# --- Fetching Logic ---
if st.session_state.download_status == 'fetching':
    with st.spinner(f"Fetching info for: {st.session_state.current_url}..."):
        try:
            # Options to get video info efficiently
            ydl_opts_info = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'noplaylist': True
            }
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info_dict = ydl.extract_info(st.session_state.current_url, download=False)
                video_title = info_dict.get('title', 'Unknown Title')
                formats = info_dict.get('formats', [])

            # Filter for video-only formats (for later merging with best audio)
            available_qualities = {}
            for f in formats:
                # Ensure it's video-only, has resolution
                if f.get('vcodec') != 'none' and f.get('height') is not None and f.get('acodec') == 'none':
                    height = f.get('height')
                    fps = f.get('fps')
                    tbr = f.get('tbr') # Target bitrate might help differentiate
                    label = f"{height}p" + (f"{int(round(fps))}" if fps and fps > 30 else "")
                    # Use a tuple for sorting (height, fps, bitrate)
                    quality_key = (height, fps if fps else 0, tbr if tbr else 0)

                    # Store the best format found for a given label (e.g., 720p)
                    if label not in available_qualities or quality_key > available_qualities[label]['key']:
                         available_qualities[label] = {
                             'label': label,
                             'height': height,
                             'fps': fps,
                             'format_id': f['format_id'],
                             'vcodec': f.get('vcodec', 'unknown'), # Store codec info
                             'key': quality_key # For sorting/selection
                         }

            if not available_qualities:
                st.session_state.error_message = "Error: No suitable video-only formats found for merging."
                st.session_state.download_status = 'error'
            else:
                # Sort qualities from highest to lowest based on the key (height, fps, bitrate)
                sorted_qualities = sorted(available_qualities.values(), key=lambda item: item['key'], reverse=True)
                st.session_state.video_info = {
                    'title': video_title,
                    'qualities': sorted_qualities,
                    'url': st.session_state.current_url
                }
                st.session_state.download_status = 'selecting'
                st.session_state.last_fetched_url = st.session_state.current_url # Mark URL as fetched

        except yt_dlp.utils.DownloadError as e:
            st.session_state.error_message = f"Error fetching video info: {e}"
            st.session_state.download_status = 'error'
        except Exception as e:
            st.session_state.error_message = f"An unexpected error occurred during info fetch: {e}"
            st.session_state.download_status = 'error'
            # Also print unexpected errors during fetch to console for debugging
            print(f"\n--- UNEXPECTED ERROR DURING FETCH ---")
            print(f"URL: {st.session_state.current_url}")
            print(f"Exception Type: {type(e)}")
            print(f"Exception Details: {e}")
            traceback.print_exc() # Print the full traceback


# --- Display Error (if fetch failed) ---
# This handles errors specifically from the 'fetching' block above
if st.session_state.download_status == 'error' and st.session_state.error_message:
    # Only display error if it hasn't been shown via st.error or the download block yet
    if not st.session_state.get("status_text_error", False):
        if "Invalid URL format entered." not in st.session_state.error_message: # Avoid repeating URL format error
            st.error(st.session_state.error_message)
            st.session_state.status_text_error = True # Flag that error was shown


# --- Display Video Info and Quality Selection ---
if st.session_state.download_status == 'selecting' and st.session_state.video_info:
    info = st.session_state.video_info
    st.divider()
    st.subheader(f"Video Found: {info['title']}")
    quality_options = [q['label'] for q in info['qualities']]

    if not quality_options:
         st.warning("No downloadable video qualities detected for merging.")
         st.session_state.download_status = 'error' # Treat as error if no options
         st.session_state.error_message = "Could not find any video quality options for merging."
         if not st.session_state.get("status_text_error", False): # Avoid duplicate display
             st.error(st.session_state.error_message)
             st.session_state.status_text_error = True
    else:
        selected_quality_label = st.radio(
            "Select Video Quality:",
            options=quality_options,
            index=0, # Default to highest quality
            key="quality_choice",
            horizontal=True
        )
        # Find the full info dictionary for the selected quality label
        chosen_quality_info = next((q for q in info['qualities'] if q['label'] == selected_quality_label), None)

        # --- Download Button & Logic ---
        if chosen_quality_info and st.button(f"Download {selected_quality_label} (MP4)", key="download_button"):
            # Reset state specifically for this download attempt
            st.session_state.download_status = 'downloading'
            st.session_state.progress = 0.0
            st.session_state.status_message = "Initializing download..."
            st.session_state.final_filename = None
            st.session_state.error_message = None
            st.session_state.status_text_success = False # Reset display flags
            st.session_state.status_text_error = False  # Reset display flags
            st.session_state.progress_bar_text = "Initializing..." # Initial progress bar text

            # --- Create placeholders for dynamic progress UI ---
            progress_container = st.container()
            progress_text = progress_container.empty()
            progress_bar = progress_container.progress(0.0, text=st.session_state.progress_bar_text)

            # --- Modified Progress Hook ---
            def hook(d):
                # --- Hook code remains the same ---
                if d['status'] == 'downloading':
                    percent_str = d.get('_percent_str', '0%').strip()
                    percent_clean = re.sub(r'\x1b\[[0-9;]*m', '', percent_str).replace('%','').strip()
                    try: progress_value = max(0.0, min(1.0, float(percent_clean) / 100.0))
                    except ValueError: progress_value = st.session_state.progress # Keep last known value
                    speed = d.get('_speed_str', 'N/A').strip(); eta = d.get('_eta_str', 'N/A').strip()
                    st.session_state.progress = progress_value
                    st.session_state.progress_bar_text = f"{int(progress_value * 100)}% | Speed: {speed} | ETA: {eta}"
                    try:
                        if st.session_state.download_status == 'downloading':
                            progress_text.markdown(f"**Status:** Downloading `{info['title']}`...")
                            progress_bar.progress(progress_value, text=st.session_state.progress_bar_text)
                    except Exception as ui_update_error: print(f"Debug: Error updating UI in hook (downloading): {ui_update_error}")
                elif d['status'] == 'finished':
                    st.session_state.progress_bar_text = "Processing/Merging..."
                    try:
                        if st.session_state.download_status == 'downloading':
                            progress_text.markdown(f"**Status:** Processing video components...")
                            progress_bar.progress(1.0, text=st.session_state.progress_bar_text)
                    except Exception as ui_update_error: print(f"Debug: Error updating UI in hook (finished): {ui_update_error}")
                elif d['status'] == 'error':
                     st.session_state.download_status = 'error'
                     st.session_state.error_message = "yt-dlp reported an error during download/processing."
                     st.session_state.progress_bar_text = "❌ Error!"
                     try:
                        if not st.session_state.get("status_text_error", False):
                            progress_text.markdown("**Status:** Error reported by downloader.")
                            progress_bar.progress(1.0, text=st.session_state.progress_bar_text)
                            st.session_state.status_text_error = True # Flag hook handled UI error
                     except Exception as ui_update_error: print(f"Debug: Error updating UI in hook (error): {ui_update_error}")
            # --- End of Hook ---

            # --- Prepare Download Options (CORRECTED) ---
            format_selector = f"{chosen_quality_info['format_id']}+bestaudio/best"
            safe_title = re.sub(r'[\\/*?:"<>|]', "", info['title'])[:100]
            quality_tag = chosen_quality_info['label']
            base_output_name = f'{safe_title} [{quality_tag}]'
            output_template = os.path.join(OUTPUT_DIR, f'{base_output_name}.%(ext)s')
            final_expected_path = os.path.join(OUTPUT_DIR, f'{base_output_name}.mp4')

            # --- yt-dlp Options with Forced Re-encoding (CORRECTED STRUCTURE) ---
            ydl_opts_download = {
                'format': format_selector,
                'outtmpl': output_template, # Where temp files might go
                'progress_hooks': [hook],
                'noplaylist': True,
                'merge_output_format': 'mp4', # Request MP4 container

                # --- Define Postprocessors (without args inside) ---
                'postprocessors': [
                    # 1. Specify the converter and target format
                    {'key': 'FFmpegVideoConvertor',
                     'preferedformat': 'mp4'},
                    # 2. Add metadata
                    {'key': 'FFmpegMetadata', 'add_metadata': True},
                    # 3. Optional: Embed subtitles
                    # {'key': 'FFmpegEmbedSubtitle'}
                ],

                # --- Pass FFmpeg args globally for postprocessing ---
                # These arguments will be added to the FFmpeg command line
                # when yt-dlp calls FFmpeg for postprocessing tasks like conversion.
                'postprocessor_args': [
                     '-c:v', 'libx264',        # Video Codec: H.264 (AVC)
                     '-c:a', 'aac',            # Audio Codec: AAC
                     '-crf', '23',             # Constant Rate Factor (Quality: ~18=high, 23=good, 28=low)
                     '-preset', 'medium',      # Encoding Speed vs Compression
                     '-pix_fmt', 'yuv420p',     # Pixel format for broad compatibility
                     '-movflags', '+faststart' # Optimize for streaming/web playback
                ],
                # --- End of FFmpeg global arguments ---

                 'quiet': True,       # Suppress yt-dlp console output
                 'no_warnings': True, # Suppress yt-dlp warnings
                 'verbose': False,    # No verbose debug output
                 'ignoreerrors': False, # Stop on download/processing errors
                 'fixup': 'warn',     # Try to fix minor issues if possible
                 # 'keepvideo': True, # Uncomment if you want to keep original downloaded files on error
            }
            # --- End of yt-dlp Options ---

            # --- Execute Download ---
            try:
                progress_text.markdown(f"**Status:** Initializing download & processing...")
                progress_bar.progress(0.0, text="Starting...")

                with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                    ydl.download([info['url']])

                # --- Post-Download Check ---
                if st.session_state.download_status != 'error':
                    if os.path.exists(final_expected_path):
                        st.session_state.download_status = 'finished'
                        st.session_state.final_filename = final_expected_path
                        st.session_state.status_message = f"Download and conversion successful: {os.path.basename(final_expected_path)}"
                        st.session_state.progress_bar_text = "✅ Download Successful!"
                        progress_text.markdown(f"**Status:** Completed!")
                        progress_bar.progress(1.0, text=st.session_state.progress_bar_text)
                        st.session_state.status_text_success = True
                    else:
                        st.session_state.download_status = 'error'
                        st.session_state.final_filename = None
                        found_other_file = None
                        try:
                            for f in os.listdir(OUTPUT_DIR):
                                if f.startswith(base_output_name): found_other_file = f; break
                        except OSError: pass
                        if found_other_file: st.session_state.error_message = f"Processing OK, but final file is '{found_other_file}' instead of '.mp4'. Check FFmpeg setup or codecs."
                        else: st.session_state.error_message = "Processing finished, but the final MP4 file was not found. FFmpeg conversion likely failed silently."
                        st.session_state.progress_bar_text = "❌ Error: Output File Issue!"
                        if not st.session_state.get("status_text_error", False):
                            progress_text.markdown("**Status:** Error during final file check.")
                            progress_bar.progress(1.0, text=st.session_state.progress_bar_text)
                            st.session_state.status_text_error = True

            except yt_dlp.utils.DownloadError as e:
                if st.session_state.download_status != 'error':
                    st.session_state.download_status = 'error'
                    err_str = str(e).lower()
                    if "ffmpeg" in err_str or "post-process" in err_str or "conversion" in err_str: st.session_state.error_message = f"Download/Conversion Error (FFmpeg issue likely): {e}. Ensure FFmpeg is installed and accessible."
                    else: st.session_state.error_message = f"yt-dlp Download Error: {e}"
                    st.session_state.progress_bar_text = "❌ Error during download/process!"
                    if not st.session_state.get("status_text_error", False):
                        try:
                            progress_text.markdown("**Status:** Error")
                            progress_bar.progress(1.0, text=st.session_state.progress_bar_text)
                        except Exception: pass
                        st.session_state.status_text_error = True

            except Exception as e: # Catch any other unexpected errors
                 if st.session_state.download_status != 'error':
                    st.session_state.download_status = 'error'
                    st.session_state.error_message = f"An unexpected error occurred: {e}"
                    # --- DEBUG PRINTING ---
                    print(f"\n--- UNEXPECTED ERROR CAUGHT DURING DOWNLOAD/PROCESS ---")
                    print(f"URL: {info.get('url', 'N/A')}")
                    print(f"Chosen Quality: {chosen_quality_info}")
                    print(f"FFmpeg Options Used (Postprocessors): {ydl_opts_download.get('postprocessors', [])}")
                    print(f"FFmpeg Options Used (Args): {ydl_opts_download.get('postprocessor_args', [])}")
                    print(f"Exception Type: {type(e)}")
                    print(f"Exception Details: {e}")
                    traceback.print_exc()
                    # --- END DEBUG PRINTING ---
                    st.session_state.progress_bar_text = "❌ Unexpected Error!"
                    if not st.session_state.get("status_text_error", False):
                        try:
                             progress_text.markdown("**Status:** Error")
                             progress_bar.progress(1.0, text=st.session_state.progress_bar_text)
                        except Exception: pass
                        st.session_state.status_text_error = True


# --- Display Download Button or Final Error Message ---
final_status_placeholder = st.empty()

if st.session_state.download_status == 'finished' and st.session_state.final_filename:
    with final_status_placeholder.container():
        try:
            with open(st.session_state.final_filename, "rb") as fp:
                st.download_button(
                    label=f"Download {os.path.basename(st.session_state.final_filename)}",
                    data=fp,
                    file_name=os.path.basename(st.session_state.final_filename),
                    mime="video/mp4",
                    key="download_final_button"
                )
        except FileNotFoundError:
            if not st.session_state.get("status_text_error", False):
                 final_status_placeholder.error(f"Error: The downloaded file '{st.session_state.final_filename}' could not be found for the download button.")
                 st.session_state.download_status = 'error'
                 st.session_state.status_text_error = True
        except Exception as e:
            if not st.session_state.get("status_text_error", False):
                 final_status_placeholder.error(f"Error reading file for download button: {e}")
                 print(f"\n--- ERROR READING FILE FOR DOWNLOAD BUTTON ---")
                 print(f"Filename: {st.session_state.final_filename}")
                 print(f"Exception Type: {type(e)}")
                 print(f"Exception Details: {e}")
                 traceback.print_exc()
                 st.session_state.download_status = 'error'
                 st.session_state.status_text_error = True

elif st.session_state.download_status == 'error' and st.session_state.error_message:
     if not st.session_state.get("status_text_error", False):
         final_status_placeholder.error(f"Failed: {st.session_state.error_message}")


# --- Footer ---
st.divider()
st.caption("Built with Streamlit & yt-dlp. Requires FFmpeg for merging and conversion.")
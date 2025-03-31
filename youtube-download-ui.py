import streamlit as st
from pytubefix import YouTube
from pytubefix.exceptions import RegexMatchError, VideoUnavailable
import re
import os
import time
import logging
import math
import subprocess # For running ffmpeg
import shutil # For checking ffmpeg path

# --- Configuration & Constants ---
DOWNLOAD_DIR = "downloads"
TEMP_DIR = os.path.join(DOWNLOAD_DIR, "temp") # Temp dir for DASH parts
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

PROGRESS_UPDATE_INTERVAL_SECS = 0.5

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---
YOUTUBE_REGEX = re.compile(
    r'(https?://)?(www\.)?'
    '(youtube|youtu|youtube-nocookie)\.(com|be)/'
    '(watch\?v=|embed/|v/|.+\?v=|shorts/|live/)?([^&=%\?]{11})'
)

def is_valid_youtube_url(url):
    return bool(YOUTUBE_REGEX.match(url))

def sanitize_filename(title):
    sanitized = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    sanitized = re.sub(r'\s+', '_', sanitized)
    # Avoid names starting with '.' or having consecutive dots
    sanitized = re.sub(r'^\.|\.\.+', '_', sanitized)
    return sanitized[:100] # Limit length

@st.cache_data(show_spinner=False) # Cache the ffmpeg check result
def check_ffmpeg():
    """Checks if ffmpeg is installed and accessible."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        logging.info(f"ffmpeg found at: {ffmpeg_path}")
        return True
    else:
        logging.error("ffmpeg not found in system PATH.")
        return False

# --- Streamlit App UI and Logic ---
st.set_page_config(page_title="YouTube Downloader (All Qualities)", layout="centered")
st.title("🎬 YouTube Video Downloader")
st.markdown("Download videos in various qualities (Progressive or DASH+Merge).")

# --- FFMPEG Check ---
ffmpeg_available = check_ffmpeg()
if not ffmpeg_available:
    st.warning("""
    **FFmpeg not found!** Merging higher quality video and audio (DASH) will not work.
    Please install FFmpeg and ensure it's in your system's PATH.
    Only lower-quality 'Progressive' downloads might be available.
    See [ffmpeg.org](https://ffmpeg.org/download.html) for installation instructions.
    """)

# --- State Management ---
default_state = {
    'video_info': None, 'error_message': None, 'download_in_progress': False,
    'download_complete': False, 'downloaded_file_path': None,
    'downloaded_file_name': None, 'downloaded_file_size': None,
    'last_submitted_url': "", 'last_progress': -1, 'last_update_time': 0,
    'streams_fetched': False, 'progressive_streams': [], 'adaptive_video_streams': [],
    'adaptive_audio_streams': [], 'download_mode': 'Progressive', # Default mode
    'merge_status': ''
}
for key, value in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- URL Input and Submission ---
url = st.text_input("Enter YouTube Video URL:", placeholder="e.g., https://www.youtube.com/watch?v=...", key="url_input")
submit_button = st.button("Fetch Video Info")

# --- Processing Logic ---
if submit_button and url:
    # Reset state if URL changes
    if url != st.session_state.last_submitted_url:
        logging.info(f"New URL submitted: {url}. Resetting state.")
        for key, value in default_state.items():
            st.session_state[key] = value
            # Keep ffmpeg check status
            st.session_state.ffmpeg_available = ffmpeg_available
        st.session_state.last_submitted_url = url

    # Validate URL
    if not is_valid_youtube_url(url):
        st.session_state.error_message = "Invalid YouTube URL format."
        st.session_state.streams_fetched = False
    # Proceed if URL is valid and different or if fetch failed previously
    elif not st.session_state.streams_fetched or url != st.session_state.last_submitted_url:
        st.session_state.error_message = None # Clear previous errors for this attempt
        st.session_state.streams_fetched = False # Mark as not fetched yet for this attempt
        st.session_state.progressive_streams = []
        st.session_state.adaptive_video_streams = []
        st.session_state.adaptive_audio_streams = []

        info_placeholder = st.empty()
        info_placeholder.info("⏳ Fetching video info and available streams...")
        try:
            logging.info(f"Fetching info for URL: {url} using pytubefix")
            yt = YouTube(url)
            yt.check_availability()
            title = yt.title
            logging.info(f"Video Title: {title}")

            # --- Fetch ALL relevant streams ---
            all_streams = yt.streams

            # Progressive MP4 (Video+Audio) - Usually max 720p
            st.session_state.progressive_streams = all_streams.filter(
                progressive=True, file_extension='mp4'
            ).order_by('resolution').desc().itag_index

            # Adaptive Video (Video Only - MP4)
            st.session_state.adaptive_video_streams = all_streams.filter(
                adaptive=True, only_video=True, file_extension='mp4'
            ).order_by('resolution').desc().itag_index

            # Adaptive Audio (Audio Only - typically m4a/mp4 or webm)
            st.session_state.adaptive_audio_streams = all_streams.filter(
                adaptive=True, only_audio=True
            ).order_by('abr').desc().itag_index # Order by bitrate

            logging.info(f"Found {len(st.session_state.progressive_streams)} progressive streams.")
            logging.info(f"Found {len(st.session_state.adaptive_video_streams)} adaptive video streams.")
            logging.info(f"Found {len(st.session_state.adaptive_audio_streams)} adaptive audio streams.")

            st.session_state.video_info = {'title': title, 'yt_object': yt}
            st.session_state.streams_fetched = True
            st.session_state.download_complete = False
            st.session_state.merge_status = ''

            # Check if any streams were found
            if not st.session_state.progressive_streams and \
               not st.session_state.adaptive_video_streams:
                st.session_state.error_message = "Could not find any downloadable video streams for this URL."
                st.session_state.streams_fetched = False # Mark as failed

        except VideoUnavailable:
            logging.error(f"VideoUnavailable for URL: {url}")
            st.session_state.error_message = "Video is unavailable (private, deleted, or restricted)."
            st.session_state.streams_fetched = False
        except RegexMatchError:
             logging.error(f"RegexMatchError for URL: {url}")
             st.session_state.error_message = "Failed to parse YouTube URL format."
             st.session_state.streams_fetched = False
        except Exception as e:
            logging.exception(f"Unexpected error fetching video info for {url}: {e}")
            st.session_state.error_message = f"An error occurred fetching info: {str(e)[:150]}..."
            st.session_state.streams_fetched = False
        finally:
             info_placeholder.empty()

# --- Display Errors or Status ---
if st.session_state.error_message and st.session_state.last_submitted_url == url:
    st.error(st.session_state.error_message)

# --- Display Options if Streams Fetched ---
if st.session_state.streams_fetched and st.session_state.last_submitted_url == url \
   and not st.session_state.download_complete and not st.session_state.download_in_progress:

    st.subheader(f"Video Title: {st.session_state.video_info['title']}")

    # --- Download Mode Selection ---
    modes = ["Progressive (Simpler, Max ~720p)"]
    if ffmpeg_available and st.session_state.adaptive_video_streams and st.session_state.adaptive_audio_streams:
        modes.append("Highest Quality (DASH - Requires Merge)")

    if len(modes) > 1:
         selected_mode = st.radio(
              "Choose Download Type:",
              options=modes,
              key="mode_radio",
              horizontal=True,
         )
         # Extract mode name for logic
         st.session_state.download_mode = "Progressive" if "Progressive" in selected_mode else "DASH"
    elif "Progressive" in modes:
         st.session_state.download_mode = "Progressive"
         st.info("Only Progressive download options available.")
    else:
         st.error("No downloadable streams found.")
         st.stop() # Stop execution if no options

    download_button_pressed = False
    selected_stream_itag = None
    selected_video_itag = None
    selected_audio_itag = None

    # --- Quality Selection UI (Conditional) ---
    st.markdown("---")
    if st.session_state.download_mode == "Progressive":
        st.subheader("Progressive Download Options")
        prog_options_dict = {}
        for itag, s in st.session_state.progressive_streams.items():
             label = f"{s.resolution} ({s.filesize_mb:.1f} MB, {s.mime_type})"
             prog_options_dict[label] = itag

        if not prog_options_dict:
            st.warning("No progressive streams found for this video.")
        else:
            selected_prog_label = st.selectbox(
                "Select Quality (Video+Audio Combined):",
                options=list(prog_options_dict.keys()),
                key="prog_quality_select"
            )
            selected_stream_itag = prog_options_dict[selected_prog_label]
            download_button_pressed = st.button(f"Download ({selected_prog_label})", key="download_prog_button")

    elif st.session_state.download_mode == "DASH":
        st.subheader("Highest Quality (DASH) Options")
        if not ffmpeg_available:
             st.error("Cannot perform DASH download because FFmpeg is missing.")
        else:
            # Video Selection
            vid_options_dict = {}
            for itag, s in st.session_state.adaptive_video_streams.items():
                label = f"{s.resolution} ({s.fps}fps, {s.filesize_mb:.1f} MB, {s.video_codec})"
                vid_options_dict[label] = itag

            selected_vid_label = st.selectbox(
                "Select Video Quality (Video Only):",
                options=list(vid_options_dict.keys()),
                key="vid_quality_select"
            )
            selected_video_itag = vid_options_dict[selected_vid_label]

            # Audio Selection
            aud_options_dict = {}
            for itag, s in st.session_state.adaptive_audio_streams.items():
                 label = f"{s.abr} ({s.filesize_mb:.1f} MB, {s.audio_codec})"
                 # Ensure unique labels if multiple streams have same abr/size/codec
                 count = 1
                 base_label = label
                 while label in aud_options_dict:
                     label = f"{base_label} #{count+1}"
                     count += 1
                 aud_options_dict[label] = itag


            selected_aud_label = st.selectbox(
                "Select Audio Quality (Audio Only):",
                options=list(aud_options_dict.keys()),
                key="aud_quality_select"
            )
            selected_audio_itag = aud_options_dict[selected_aud_label]

            download_button_pressed = st.button(f"Download & Merge ({vid_options_dict[selected_vid_label]} + {aud_options_dict[selected_aud_label]})", key="download_dash_button")


    # --- Download Execution ---
    if download_button_pressed:
        st.session_state.download_in_progress = True
        st.session_state.error_message = None
        st.session_state.download_complete = False
        st.session_state.downloaded_file_path = None
        st.session_state.merge_status = ''
        st.session_state.last_progress = -1
        st.session_state.last_update_time = 0

        progress_bar_placeholder = st.empty()
        status_text_placeholder = st.empty()
        progress_bar = progress_bar_placeholder.progress(0)
        status_text = status_text_placeholder.info("🚀 Initializing...")
        start_time = time.time()

        # --- Progress Callback ---
        def progress_callback(stream, chunk, bytes_remaining):
            current_time = time.time()
            total_size = stream.filesize or 0 # Handle None filesize
            if total_size == 0: return # Cannot calculate percentage

            bytes_downloaded = total_size - bytes_remaining
            percentage = int((bytes_downloaded / total_size) * 100)

            # Determine phase for combined progress bar (optional complexity)
            # Simple approach: Update bar per file, reset in between
            progress_bar.progress(percentage) # Update for current file

            if percentage > st.session_state.last_progress or \
               (current_time - st.session_state.last_update_time) > PROGRESS_UPDATE_INTERVAL_SECS:
                elapsed_time = current_time - start_time # Use overall start time
                speed_mbps = (bytes_downloaded / (elapsed_time + 1e-9)) / (1024 * 1024)
                eta_seconds = (bytes_remaining / (bytes_downloaded / (elapsed_time + 1e-9))) if bytes_downloaded > 0 else 0

                # Update status text based on current operation (set outside callback)
                current_status = st.session_state.get('current_download_phase', 'Downloading')
                status_text.info(
                    f"⏳ {current_status}... {percentage}% "
                    f"({bytes_downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB) | "
                    f"Speed: {speed_mbps:.2f} MB/s | "
                    f"ETA: {math.ceil(eta_seconds)}s"
                )
                st.session_state.last_progress = percentage
                st.session_state.last_update_time = current_time

        # --- Get YT object ---
        if 'yt_object' not in st.session_state.video_info:
            st.error("Session expired or invalid. Please fetch video info again.")
            st.session_state.download_in_progress = False
            st.stop()
        yt = st.session_state.video_info['yt_object']
        yt.register_on_progress_callback(progress_callback) # Register callback

        # --- Download Path ---
        try:
            if st.session_state.download_mode == "Progressive" and selected_stream_itag:
                st.session_state.current_download_phase = "Downloading Progressive"
                stream_to_download = yt.streams.get_by_itag(selected_stream_itag)
                if not stream_to_download: raise Exception(f"Progressive stream {selected_stream_itag} not found.")

                status_text.info(f"Downloading {stream_to_download.resolution}...")
                st.session_state.last_progress = -1 # Reset progress for this file
                st.session_state.last_update_time = time.time()

                base_filename = sanitize_filename(st.session_state.video_info['title'])
                quality_tag = stream_to_download.resolution or "prog"
                final_filename = f"{base_filename}_{quality_tag}.mp4"
                st.session_state.downloaded_file_name = final_filename

                downloaded_path = stream_to_download.download(
                    output_path=DOWNLOAD_DIR, filename=final_filename
                )
                st.session_state.downloaded_file_path = downloaded_path

            elif st.session_state.download_mode == "DASH" and selected_video_itag and selected_audio_itag:
                if not ffmpeg_available: raise Exception("FFmpeg is required for DASH downloads but not found.")

                video_stream = yt.streams.get_by_itag(selected_video_itag)
                audio_stream = yt.streams.get_by_itag(selected_audio_itag)
                if not video_stream: raise Exception(f"Video stream {selected_video_itag} not found.")
                if not audio_stream: raise Exception(f"Audio stream {selected_audio_itag} not found.")

                base_filename = sanitize_filename(st.session_state.video_info['title'])
                vid_res_tag = video_stream.resolution or "vid"
                aud_abr_tag = audio_stream.abr or "aud"
                final_filename = f"{base_filename}_{vid_res_tag}_{aud_abr_tag}.mp4"
                st.session_state.downloaded_file_name = final_filename
                final_filepath = os.path.join(DOWNLOAD_DIR, final_filename)

                # Temporary file paths
                temp_video_path = os.path.join(TEMP_DIR, f"{base_filename}_vid.mp4")
                # Audio extension might not be mp4, use what pytube gives if possible
                temp_audio_ext = audio_stream.mime_type.split('/')[-1]
                temp_audio_path = os.path.join(TEMP_DIR, f"{base_filename}_aud.{temp_audio_ext}")

                # --- Download Video ---
                st.session_state.current_download_phase = "Downloading Video"
                status_text.info(f"Downloading Video ({video_stream.resolution})...")
                st.session_state.last_progress = -1 # Reset progress
                st.session_state.last_update_time = time.time()
                logging.info(f"Downloading video to {temp_video_path}")
                video_stream.download(output_path=TEMP_DIR, filename=os.path.basename(temp_video_path))
                logging.info("Video download complete.")

                 # --- Download Audio ---
                st.session_state.current_download_phase = "Downloading Audio"
                status_text.info(f"Downloading Audio ({audio_stream.abr})...")
                progress_bar.progress(0) # Reset progress bar for audio
                st.session_state.last_progress = -1
                st.session_state.last_update_time = time.time()
                logging.info(f"Downloading audio to {temp_audio_path}")
                audio_stream.download(output_path=TEMP_DIR, filename=os.path.basename(temp_audio_path))
                logging.info("Audio download complete.")

                # --- Merge with FFmpeg ---
                yt.register_on_progress_callback(None) # Unregister callback before merging
                progress_bar_placeholder.empty() # Remove progress bar
                st.session_state.merge_status = "⏳ Merging video and audio using FFmpeg... (may take a moment)"
                status_text.info(st.session_state.merge_status)
                logging.info(f"Merging with ffmpeg: video={temp_video_path}, audio={temp_audio_path}, output={final_filepath}")

                ffmpeg_command = [
                    'ffmpeg',
                    '-i', temp_video_path,  # Input video
                    '-i', temp_audio_path,  # Input audio
                    '-c:v', 'copy',         # Copy video codec (fast)
                    '-c:a', 'copy',         # Copy audio codec (fast)
                    '-loglevel', 'error',   # Show only errors from ffmpeg
                    final_filepath          # Output file path
                ]

                try:
                    process = subprocess.run(ffmpeg_command, check=True, capture_output=True, text=True)
                    logging.info("FFmpeg merge successful.")
                    st.session_state.merge_status = "✅ Merging complete!"
                    status_text.success(st.session_state.merge_status)
                    st.session_state.downloaded_file_path = final_filepath # Set final path
                except subprocess.CalledProcessError as e:
                    logging.error(f"FFmpeg merge failed. Return code: {e.returncode}")
                    logging.error(f"FFmpeg stderr: {e.stderr}")
                    st.session_state.merge_status = f"❌ FFmpeg merge failed: {e.stderr[:200]}..." # Show part of error
                    raise Exception(f"FFmpeg failed: {e.stderr}") # Propagate error
                finally:
                    # --- Cleanup Temp Files ---
                    logging.info("Cleaning up temporary files...")
                    if os.path.exists(temp_video_path): os.remove(temp_video_path)
                    if os.path.exists(temp_audio_path): os.remove(temp_audio_path)
                    logging.info("Temporary files cleaned.")

            else:
                raise Exception("No valid download option selected or available.")

            # --- Final Checks Post-Download/Merge ---
            if not st.session_state.downloaded_file_path or \
               not os.path.exists(st.session_state.downloaded_file_path) or \
               os.path.getsize(st.session_state.downloaded_file_path) == 0:
                 raise Exception("Final file is missing or empty after download/merge.")

            st.session_state.downloaded_file_size = os.path.getsize(st.session_state.downloaded_file_path)
            st.session_state.download_complete = True
            st.session_state.error_message = None

        except Exception as e:
            logging.exception(f"Error during download/merge process: {e}")
            st.session_state.error_message = f"An error occurred: {str(e)[:200]}..."
            st.session_state.download_complete = False
            st.session_state.downloaded_file_path = None
            # Clear progress indicators on error
            progress_bar_placeholder.empty()
            status_text_placeholder.empty()

        finally:
            # --- Final Cleanup ---
            st.session_state.download_in_progress = False
            st.session_state.current_download_phase = '' # Clear phase status
            # Ensure callback is unregistered
            if 'yt' in locals() and yt:
                 try: yt.register_on_progress_callback(None)
                 except Exception: pass
             # Hide merge status if it was showing an error or is irrelevant now
            if st.session_state.error_message and "Merging" in st.session_state.merge_status:
                 pass # Keep merge status if it's part of the error
            elif status_text is not None and not st.session_state.download_complete:
                 status_text_placeholder.empty() # Clear status text if download failed elsewhere


# --- Download Completion & Access ---
if st.session_state.download_complete and st.session_state.downloaded_file_path:
    # Ensure status text from download doesn't linger if merge status wasn't shown
    if 'status_text_placeholder' in locals(): status_text_placeholder.empty()

    st.success(f"✅ Download successful! ({st.session_state.download_mode})")
    if st.session_state.merge_status and "complete" in st.session_state.merge_status:
         st.success(st.session_state.merge_status) # Show merge success again if applicable

    st.info(f"File: **{st.session_state.downloaded_file_name}** | Size: **{st.session_state.downloaded_file_size / (1024 * 1024):.2f} MB**")
    try:
        with open(st.session_state.downloaded_file_path, "rb") as file_data:
            st.download_button(
                label="📥 Save Video to Your Device",
                data=file_data,
                file_name=st.session_state.downloaded_file_name,
                mime="video/mp4",
                key="save_button"
            )
    except FileNotFoundError:
        st.error("Error: Downloaded file not found. Please try again.")
        st.session_state.download_complete = False
        st.session_state.downloaded_file_path = None
    except Exception as e:
         st.error(f"An error occurred preparing download link: {e}")
         logging.exception("Error preparing download link.")
         st.session_state.download_complete = False
         st.session_state.downloaded_file_path = None

# --- Footer ---
st.markdown("---")
st.caption("Remember to respect copyright and YouTube's Terms of Service. DASH downloads require FFmpeg.")
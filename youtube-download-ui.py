import streamlit as st
from pytubefix import YouTube
from pytubefix.exceptions import RegexMatchError, VideoUnavailable
import re
import os
import time
import logging
import math
import subprocess
import shutil

# --- Constants ---
DOWNLOAD_DIR = "downloads"
TEMP_DIR_NAME = "temp"
PROGRESS_UPDATE_INTERVAL_SECS = 0.5
MODE_AUTO = "DASH_Auto"
MODE_MANUAL = "DASH_Manual"
MODE_PROGRESSIVE = "Progressive"
MODE_LABEL_AUTO = "✨ Best Quality (DASH + Merge - Auto)"
MODE_LABEL_MANUAL = "⚙️ Manual Quality (DASH + Merge)"
MODE_LABEL_PROGRESSIVE = "🚀 Progressive (Simple, Max ~720p)"

# --- Logging Setup ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s')
log_handler = logging.StreamHandler()
log_handler.setFormatter(log_formatter)
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(log_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

# --- Helper Functions ---
YOUTUBE_REGEX = re.compile(r'(https?://)?((www|m)\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)([^&?/\s]{11})')

def is_valid_youtube_url(url: str) -> bool:
    if not url: return False
    return bool(YOUTUBE_REGEX.match(url))

def sanitize_filename(title: str) -> str:
    if not title: return "downloaded_video"
    sanitized = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    sanitized = re.sub(r'\s+', '_', sanitized)
    sanitized = sanitized.strip('_.- ')
    return sanitized[:100] if len(sanitized) > 100 else sanitized

@st.cache_data(show_spinner=False)
def check_ffmpeg() -> bool:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path: logger.info(f"ffmpeg found: {ffmpeg_path}"); return True
    else: logger.error("ffmpeg not found in PATH."); return False

# --- State Initialization ---
DEFAULT_STATE = {
    'video_info': None, 'error_message': None, 'download_in_progress': False,
    'download_complete': False, 'downloaded_file_path': None,
    'downloaded_file_name': None, 'downloaded_file_size': None,
    'last_submitted_url': "", 'last_fetched_url':"", 'last_progress': -1, 'last_update_time': 0,
    'streams_fetched': False, 'progressive_streams': {}, 'adaptive_video_streams': {},
    'adaptive_audio_streams': {}, 'download_mode': MODE_AUTO,
    'merge_status': '', 'current_download_phase': '',
    'ffmpeg_available': check_ffmpeg(),
}
for key, value in DEFAULT_STATE.items():
    if key not in st.session_state: st.session_state[key] = value
if 'ffmpeg_available' not in st.session_state: st.session_state.ffmpeg_available = check_ffmpeg()

def reset_download_state():
    logger.info("Resetting download state.")
    keys_to_reset = ['video_info', 'error_message', 'download_in_progress',
                     'download_complete', 'downloaded_file_path', 'downloaded_file_name',
                     'downloaded_file_size', 'last_progress', 'last_update_time',
                     'streams_fetched', 'progressive_streams', 'adaptive_video_streams',
                     'adaptive_audio_streams', 'merge_status', 'current_download_phase']
    for key in keys_to_reset: st.session_state[key] = DEFAULT_STATE.get(key) # Use .get for safety

def handle_url_change():
    current_url = st.session_state.get("url_input_widget", "")
    last_submitted = st.session_state.last_submitted_url
    if st.session_state.download_complete and current_url and current_url != last_submitted and is_valid_youtube_url(current_url):
        logger.info(f"New valid URL via change: {current_url}")
        st.session_state.last_submitted_url = current_url
        reset_download_state()

# --- Streamlit App UI ---
st.set_page_config(page_title="YouTube Downloader Pro+", layout="centered", initial_sidebar_state="collapsed")

# --- Centered, Two-Line Title using Markdown ---
st.markdown("""
<div style='text-align: center;'>
    <h1>🎬 YouTube Video Downloader<br>Pro+</h1>
</div>
""", unsafe_allow_html=True)
# --- End Title Change ---


st.markdown("""
Welcome! Save YouTube videos for offline viewing right here.

Simply **paste a YouTube video link** below and click **Fetch Video Info**.

You can then choose your preferred download type:
*   **Best Quality:** Gets the highest resolution video and best audio, merged automatically.
*   **Manual Quality:** Pick specific video and audio qualities for merging.
*   **Progressive:** A simpler, single-file download (usually up to 720p).
""")
st.divider()

if not st.session_state.ffmpeg_available:
    st.warning("""
    **FFmpeg Not Found!**
    The 'Best Quality' and 'Manual Quality' options require **FFmpeg** to combine video and audio files.
    'Progressive' downloads will still work if available.

    *   Please install FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) and add it to your system's PATH to enable all features.
    """, icon="⚠️")

# --- URL Input Area ---
url = st.text_input(
    "**Enter YouTube Video URL:**",
    placeholder="e.g., https://www.youtube.com/watch?v=...",
    key="url_input_widget",
    on_change=handle_url_change,
    label_visibility="collapsed"
)
submit_button = st.button("Fetch Video Info", key="fetch_button", type="primary", use_container_width=True)

# --- Determine if Fetch is Needed ---
should_fetch = False
current_input_url = st.session_state.get("url_input_widget", "")
if submit_button and current_input_url:
    logger.info(f"Fetch btn clicked: {current_input_url}")
    st.session_state.last_submitted_url = current_input_url
    reset_download_state()
    if is_valid_youtube_url(current_input_url): should_fetch = True
    else: st.session_state.error_message = "Invalid YouTube URL format."; should_fetch = False
elif current_input_url == st.session_state.last_submitted_url and not st.session_state.streams_fetched and \
     not st.session_state.error_message and is_valid_youtube_url(current_input_url) and \
     st.session_state.last_fetched_url != current_input_url:
     logger.info(f"Auto-fetch triggered: {current_input_url}"); should_fetch = True

# --- Processing Logic (Fetch Streams) ---
if should_fetch:
    fetch_url = st.session_state.last_submitted_url
    if not is_valid_youtube_url(fetch_url): st.session_state.error_message = "Invalid URL."
    else:
        st.session_state.error_message = None; st.session_state.streams_fetched = False
        info_placeholder = st.empty(); info_placeholder.info("⏳ Fetching video information...")
        try:
            logger.info(f"Fetching: {fetch_url}")
            yt = YouTube(fetch_url)
            try: yt.check_availability()
            except VideoUnavailable as ve: logger.warning(f"Availability check warn ({ve}), continuing fetch.")
            title = yt.title; logger.info(f"Title: {title}")
            all_streams = yt.streams
            st.session_state.progressive_streams = all_streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().itag_index
            st.session_state.adaptive_video_streams = all_streams.filter(adaptive=True, only_video=True, file_extension='mp4').order_by('resolution').desc().itag_index
            st.session_state.adaptive_audio_streams = all_streams.filter(adaptive=True, only_audio=True).order_by('abr').desc().itag_index
            logger.info(f"Streams: P={len(st.session_state.progressive_streams)}, AV={len(st.session_state.adaptive_video_streams)}, AA={len(st.session_state.adaptive_audio_streams)}")
            st.session_state.video_info = {'title': title, 'yt_object': yt}; st.session_state.streams_fetched = True
            st.session_state.download_complete = False; st.session_state.merge_status = ''; st.session_state.last_fetched_url = fetch_url
            if not st.session_state.progressive_streams and not st.session_state.adaptive_video_streams:
                st.session_state.error_message = "No downloadable MP4 video streams found."; st.session_state.streams_fetched = False
        except VideoUnavailable: logger.error(f"Unavailable: {fetch_url}"); st.session_state.error_message = "Video unavailable (private, deleted, restricted)."; st.session_state.streams_fetched = False
        except RegexMatchError: logger.error(f"Regex fail: {fetch_url}"); st.session_state.error_message = "Invalid YouTube URL format."; st.session_state.streams_fetched = False
        except Exception as e: logger.exception(f"Fetch error: {fetch_url}"); st.session_state.error_message = f"Fetch error: {str(e)[:150]}..."; st.session_state.streams_fetched = False
        finally: info_placeholder.empty()

# --- Display Errors (If any) ---
if st.session_state.error_message and st.session_state.last_submitted_url == current_input_url:
    st.error(st.session_state.error_message, icon="🚨")

# --- Display Download Options UI ---
if st.session_state.streams_fetched and st.session_state.last_fetched_url == current_input_url \
   and not st.session_state.download_in_progress and not st.session_state.download_complete:

    st.divider()
    st.subheader(f"🎬 Video Found: {st.session_state.video_info['title']}")

    available_modes_map = {}
    dash_possible = (st.session_state.ffmpeg_available and st.session_state.adaptive_video_streams and st.session_state.adaptive_audio_streams)
    if dash_possible: available_modes_map[MODE_LABEL_AUTO] = MODE_AUTO
    if dash_possible: available_modes_map[MODE_LABEL_MANUAL] = MODE_MANUAL
    if st.session_state.progressive_streams: available_modes_map[MODE_LABEL_PROGRESSIVE] = MODE_PROGRESSIVE

    if not available_modes_map: st.warning("No downloadable options found."); st.stop()
    available_mode_labels = list(available_modes_map.keys())
    default_index = 0
    if MODE_LABEL_AUTO in available_mode_labels: default_index = available_mode_labels.index(MODE_LABEL_AUTO)
    elif MODE_LABEL_MANUAL in available_mode_labels: default_index = available_mode_labels.index(MODE_LABEL_MANUAL)

    st.markdown("**Choose Download Option:**")
    selected_mode_label = st.radio("Download Options", options=available_mode_labels, index=default_index, key="mode_radio", horizontal=True, label_visibility="collapsed")
    st.session_state.download_mode = available_modes_map[selected_mode_label]

    trigger_download = False; selected_stream_itag = None; selected_video_itag_manual = None; selected_audio_itag_manual = None
    st.divider()

    container = st.container(border=True)

    if st.session_state.download_mode == MODE_PROGRESSIVE:
        container.markdown("##### 🚀 Progressive (Single File)")
        container.caption("Downloads video and audio combined. Good compatibility, max 720p usually.")
        prog_opts = {f"{s.resolution} ({s.filesize_mb:.1f}MB)": itag for itag, s in st.session_state.progressive_streams.items() if s.resolution and getattr(s, 'filesize_mb', None) is not None}
        if prog_opts:
             sel_lbl = container.selectbox("Select Quality:", prog_opts.keys(), key="prog_sel")
             selected_stream_itag = prog_opts[sel_lbl]
             trigger_download = container.button(f"Download ({sel_lbl})", key="dl_prog", type="primary")
        else: container.info("No progressive options available.")

    elif st.session_state.download_mode == MODE_MANUAL:
        container.markdown("##### ⚙️ Manual Quality (Separate Files + Merge)")
        container.caption("Requires FFmpeg. Choose specific video & audio streams.")
        col1, col2 = container.columns(2)
        with col1:
            vid_opts = {f"V: {s.resolution} {s.fps}fps ({s.filesize_mb:.1f}MB) {s.video_codec}": itag for itag, s in st.session_state.adaptive_video_streams.items() if s.resolution and getattr(s, 'filesize_mb', None) is not None}
            if vid_opts: sel_vid_lbl = st.selectbox("Video Stream:", vid_opts.keys(), key="vid_sel"); selected_video_itag_manual = vid_opts[sel_vid_lbl]
            else: st.warning("No video streams.")
        with col2:
            aud_opts = {}
            for itag, s in st.session_state.adaptive_audio_streams.items():
                if getattr(s, 'abr', None) and getattr(s, 'filesize_mb', None) is not None:
                    lbl = f"A: {s.abr} ({s.filesize_mb:.1f}MB) {s.audio_codec or ''}"; base=lbl; c=1
                    while lbl in aud_opts: lbl = f"{base}_{c+1}"; c+=1
                    aud_opts[lbl] = itag
            if aud_opts: sel_aud_lbl = st.selectbox("Audio Stream:", aud_opts.keys(), key="aud_sel"); selected_audio_itag_manual = aud_opts[sel_aud_lbl]
            else: st.warning("No audio streams.")
        if selected_video_itag_manual and selected_audio_itag_manual: trigger_download = container.button(f"Download & Merge Selected", key="dl_dash_manual", type="primary")
        else: container.button(f"Download & Merge Selected", key="dl_dash_manual", disabled=True)

    elif st.session_state.download_mode == MODE_AUTO:
        container.markdown("##### ✨ Best Quality (Auto-Selected)")
        container.caption("Requires FFmpeg. Automatically picks best video and best non-Opus audio.")
        best_vid_stream = st.session_state.adaptive_video_streams.get(list(st.session_state.adaptive_video_streams.keys())[0]) if st.session_state.adaptive_video_streams else None
        non_opus = { itag: s for itag, s in st.session_state.adaptive_audio_streams.items() if getattr(s, 'audio_codec', '') and 'opus' not in s.audio_codec.lower()}
        best_aud_stream = st.session_state.adaptive_audio_streams.get(list(non_opus.keys())[0]) if non_opus else (st.session_state.adaptive_audio_streams.get(list(st.session_state.adaptive_audio_streams.keys())[0]) if st.session_state.adaptive_audio_streams else None)
        if best_vid_stream: container.write(f"Best Video: {best_vid_stream.resolution} {best_vid_stream.fps}fps")
        if best_aud_stream: container.write(f"Best Audio: {best_aud_stream.abr} ({best_aud_stream.audio_codec})")
        trigger_download = container.button("Download Best Quality", key="dl_dash_auto", type="primary")

    # --- Download Execution ---
    if trigger_download:
        st.session_state.download_in_progress = True; st.session_state.error_message = None
        st.session_state.download_complete = False; st.session_state.downloaded_file_path = None
        st.session_state.merge_status = ''; st.session_state.last_progress = -1; st.session_state.last_update_time = 0
        progress_bar_placeholder = st.empty(); status_text_placeholder = st.empty()
        progress_bar = progress_bar_placeholder.progress(0); status_text = status_text_placeholder.info("🚀 Initializing...")
        start_time = time.time()

        def progress_callback(stream, chunk, bytes_remaining):
            current_time = time.time(); total_size = getattr(stream, 'filesize', 0) or 0
            if total_size == 0: return
            bytes_downloaded = total_size - bytes_remaining; percentage = min(100, int((bytes_downloaded / total_size) * 100))
            try: progress_bar.progress(percentage)
            except: pass
            if percentage > st.session_state.last_progress or (current_time - st.session_state.last_update_time) > PROGRESS_UPDATE_INTERVAL_SECS:
                elapsed_time = current_time - start_time; speed_mbps = (bytes_downloaded / (elapsed_time + 1e-9)) / (1024 * 1024)
                eta_seconds = (bytes_remaining / (bytes_downloaded / (elapsed_time + 1e-9))) if bytes_downloaded > 0 else 0
                current_status = st.session_state.get('current_download_phase', 'Downloading')
                try: status_text.info(f"⏳ {current_status}... {percentage}% ({bytes_downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB) | Speed: {speed_mbps:.2f} MB/s | ETA: {math.ceil(eta_seconds)}s")
                except: pass
                st.session_state.last_progress = percentage; st.session_state.last_update_time = current_time

        if 'yt_object' not in st.session_state.video_info: st.error("Session error."); st.session_state.download_in_progress = False; st.stop()
        yt = st.session_state.video_info['yt_object']
        yt.register_on_progress_callback(progress_callback)
        selected_video_itag = None; selected_audio_itag = None
        mode_to_execute = st.session_state.download_mode

        try:
            if mode_to_execute == MODE_PROGRESSIVE:
                if not selected_stream_itag: raise ValueError("Progressive stream missing.")
            elif mode_to_execute == MODE_MANUAL:
                if not selected_video_itag_manual or not selected_audio_itag_manual: raise ValueError("Manual DASH streams missing.")
                selected_video_itag = selected_video_itag_manual; selected_audio_itag = selected_audio_itag_manual
            elif mode_to_execute == MODE_AUTO:
                logger.info("Auto-selecting...")
                if not st.session_state.adaptive_video_streams: raise ValueError("No video for auto.")
                selected_video_itag = list(st.session_state.adaptive_video_streams.keys())[0]
                non_opus = { itag: s for itag, s in st.session_state.adaptive_audio_streams.items() if getattr(s, 'audio_codec', '') and 'opus' not in s.audio_codec.lower()}
                if non_opus: selected_audio_itag = list(non_opus.keys())[0]; logger.info(f"Auto non-opus: {selected_audio_itag}")
                elif st.session_state.adaptive_audio_streams: selected_audio_itag = list(st.session_state.adaptive_audio_streams.keys())[0]; logger.warning(f"Auto fallback audio: {selected_audio_itag}")
                else: raise ValueError("No audio for auto.")
                logger.info(f"Auto video: {selected_video_itag}")

            base_filename = sanitize_filename(st.session_state.video_info['title'])
            temp_dir_path = os.path.join(DOWNLOAD_DIR, TEMP_DIR_NAME)

            if mode_to_execute == MODE_PROGRESSIVE:
                st.session_state.current_download_phase = "Downloading Combined Video/Audio"
                stream = yt.streams.get_by_itag(selected_stream_itag); assert stream, "Prog stream invalid"
                status_text.info(f"Downloading {stream.resolution}..."); st.session_state.last_progress = -1; st.session_state.last_update_time = time.time()
                qual_tag = stream.resolution or "prog"; final_fn = f"{base_filename}_{qual_tag}.mp4"; st.session_state.downloaded_file_name = final_fn
                st.session_state.downloaded_file_path = stream.download(DOWNLOAD_DIR, final_fn)

            elif mode_to_execute in [MODE_MANUAL, MODE_AUTO]:
                assert selected_video_itag and selected_audio_itag and st.session_state.ffmpeg_available, "DASH pre-req failed"
                video_stream = yt.streams.get_by_itag(selected_video_itag); audio_stream = yt.streams.get_by_itag(selected_audio_itag); assert video_stream and audio_stream, "DASH stream invalid"
                vid_tag = video_stream.resolution or "vid"; aud_tag = audio_stream.abr or "aud"; final_fn = f"{base_filename}_{vid_tag}_{aud_tag}.mp4"; st.session_state.downloaded_file_name = final_fn
                final_filepath = os.path.join(DOWNLOAD_DIR, final_fn)
                os.makedirs(temp_dir_path, exist_ok=True)
                temp_video_fn = f"{base_filename}_vid.mp4"; audio_mime = getattr(audio_stream, 'mime_type', 'audio/mp4'); temp_audio_ext = audio_mime.split('/')[-1].split(';')[0] if '/' in audio_mime else 'm4a'; temp_audio_fn = f"{base_filename}_aud.{temp_audio_ext or 'm4a'}"
                temp_video_path = os.path.join(temp_dir_path, temp_video_fn); temp_audio_path = os.path.join(temp_dir_path, temp_audio_fn)

                st.session_state.current_download_phase = "Downloading Video"; status_text.info(f"DL Video ({video_stream.resolution})..."); st.session_state.last_progress = -1; st.session_state.last_update_time = time.time(); logger.info(f"DL video->{temp_video_path}"); video_stream.download(temp_dir_path, temp_video_fn); logger.info("Video done.")
                st.session_state.current_download_phase = "Downloading Audio"; status_text.info(f"DL Audio ({audio_stream.abr})..."); progress_bar.progress(0); st.session_state.last_progress = -1; st.session_state.last_update_time = time.time(); logger.info(f"DL audio->{temp_audio_path}"); audio_stream.download(temp_dir_path, temp_audio_fn); logger.info("Audio done.")
                yt.register_on_progress_callback(None); progress_bar_placeholder.empty()
                st.session_state.merge_status = "⏳ Merging files..."; status_text.info(st.session_state.merge_status); logger.info(f"Merging V='{temp_video_path}', A='{temp_audio_path}', O='{final_filepath}'"); assert os.path.exists(temp_video_path) and os.path.exists(temp_audio_path), "Temp files missing"
                ffmpeg_cmd = ['ffmpeg', '-y', '-i', temp_video_path, '-i', temp_audio_path, '-c', 'copy', '-loglevel', 'error', final_filepath]
                try: subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True, encoding='utf-8'); logger.info("FFmpeg OK."); st.session_state.merge_status = "✅ Merge OK!"; st.session_state.downloaded_file_path = final_filepath
                except subprocess.CalledProcessError as e: logger.error(f"FFmpeg Fail {e.returncode}: {e.stderr}"); st.session_state.merge_status = f"❌ Merge Fail: {e.stderr[:200]}..."; raise RuntimeError(f"FFmpeg failed: {e.stderr}")
                finally:
                    logger.info("Cleaning temps...");
                    try:
                        if os.path.exists(temp_video_path): os.remove(temp_video_path)
                        if os.path.exists(temp_audio_path): os.remove(temp_audio_path)
                        if os.path.exists(temp_dir_path) and not os.listdir(temp_dir_path): os.rmdir(temp_dir_path)
                    except OSError as e: logger.error(f"Error cleaning temp files: {e}")
                    logger.info("Temps cleaned.")

            assert st.session_state.downloaded_file_path and os.path.exists(st.session_state.downloaded_file_path) and os.path.getsize(st.session_state.downloaded_file_path) > 0, "Final file invalid"
            st.session_state.downloaded_file_size = os.path.getsize(st.session_state.downloaded_file_path)
            st.session_state.download_complete = True; st.session_state.error_message = None
            progress_bar_placeholder.empty(); status_text_placeholder.empty()

        except Exception as e:
            logger.exception(f"DL/Merge Error: {e}"); st.session_state.error_message = f"Download Error: {str(e)[:200]}...";
            st.session_state.download_complete = False; st.session_state.downloaded_file_path = None
            try: progress_bar_placeholder.empty(); status_text_placeholder.empty()
            except: pass
        finally:
             st.session_state.download_in_progress = False; st.session_state.current_download_phase = ''
             if 'yt' in locals() and yt:
                  try: yt.register_on_progress_callback(None)
                  except: pass

# --- Display Download Link Section ---
if st.session_state.download_complete and st.session_state.last_fetched_url == current_input_url:
    st.divider()
    st.success(f"✅ **Download Successful!**")
    if st.session_state.merge_status and "ok" in st.session_state.merge_status.lower(): st.success(st.session_state.merge_status)
    st.markdown(f"**File:** `{st.session_state.downloaded_file_name}` | **Size:** `{st.session_state.downloaded_file_size / (1024 * 1024):.2f} MB`")
    try:
        file_path = st.session_state.downloaded_file_path
        assert file_path and os.path.exists(file_path), "File path invalid for download button"
        with open(file_path, "rb") as file_data:
            st.download_button(
                label="📥 Save Video to Your Device",
                data=file_data,
                file_name=st.session_state.downloaded_file_name,
                mime="video/mp4",
                key="save_button",
                use_container_width=True,
                type="primary"
            )
        st.info("✨ **Want another video?** Paste a new URL in the box above!")
    except (FileNotFoundError, AssertionError) as fe: st.error(f"Error: Downloaded file missing ({fe})."); reset_download_state()
    except Exception as e: st.error(f"Error preparing link: {e}"); logger.exception("Link prep error."); reset_download_state()

# --- Footer ---
st.divider()
st.caption("Disclaimer: Please respect copyright laws and YouTube's Terms of Service. FFmpeg is used for best quality options.")
# st.expander("Debug State").write(st.session_state)
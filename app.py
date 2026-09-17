import os
import sys
import time
import json
import urllib.parse
import threading
from datetime import datetime
import requests
import streamlit as st

# Streamlit Page Config
st.set_page_config(
    page_title="RRB PYQ Cloud Uploader",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MASTER_CATALOG_FILE = os.path.join(DATA_DIR, "master_catalog.json")
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "upload_progress.json")
DEFAULT_CHAT_ID = "-1004342935047"

# ----------------- Security & Tokens -----------------
def get_secret(key, default=""):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)

# ----------------- Data Loading -----------------
@st.cache_data
def load_catalog():
    if not os.path.exists(MASTER_CATALOG_FILE):
        return {}
    with open(MASTER_CATALOG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# ----------------- Upload Engine (Singleton) -----------------
class UploadEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UploadEngine, cls).__new__(cls)
            cls._instance.lock = threading.RLock()
            cls._instance.is_running = False
            cls._instance.is_paused = False
            cls._instance.logs = []
            cls._instance.worker_threads = []
            cls._instance.queue = []
            cls._instance.total_queued = 0
            cls._instance.current_item = None
            cls._instance.progress = cls._instance.load_progress()
        return cls._instance

    def load_progress(self):
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"sent_urls": [], "sent_sections": [], "failed": {}}

    def save_progress(self):
        with self.lock:
            try:
                tmp = PROGRESS_FILE + ".tmp"
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(self.progress, f, indent=2)
                os.replace(tmp, PROGRESS_FILE)
            except Exception as e:
                self.log(f"Error saving progress: {e}")

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        with self.lock:
            self.logs.append(line)
            if len(self.logs) > 300:
                self.logs.pop(0)

    def build_caption(self, paper):
        year = paper.get('year', '')
        level = paper.get('level', paper.get('exam', 'RRB'))
        stage = paper.get('stage', paper.get('cbt', 'CBT'))
        dt = paper.get('date', '')
        sh = paper.get('shift', '')
        lang = paper.get('language', 'Standard')

        caption = (
            f"📑 {paper.get('exam', 'RRB')} Previous Year Paper\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 Year: {year}\n"
            f"🎓 Category: {level}\n"
            f"🎯 Stage: {stage}\n"
            f"📅 Date: {dt}\n"
            f"⏰ Shift: {sh}\n"
            f"🌐 Language: {lang}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📢 Channel: @rrballpyq"
        )
        return caption

    def send_banner_if_needed(self, bot_token, section_name, section_count, chat_id):
        with self.lock:
            if section_name in self.progress.get('sent_sections', []):
                return
            self.progress.setdefault('sent_sections', []).append(section_name)
            self.save_progress()

        banner_text = (
            f"══════════════════════════\n"
            f"📚 {section_name}\n"
            f"📊 Total Papers: {section_count}\n"
            f"══════════════════════════"
        )
        try:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                data={'chat_id': chat_id, 'text': banner_text},
                timeout=20
            )
            self.log(f"📌 Section Banner Posted: {section_name}")
        except Exception as e:
            self.log(f"Banner send error: {e}")

    def send_document(self, bot_idx, bot_token, chat_id, paper, item_idx, total_items):
        bot_name = f"Bot-{bot_idx + 1}"
        url = paper['url']
        caption = self.build_caption(paper)
        api_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

        max_retries = 4
        for attempt in range(max_retries):
            if not self.is_running:
                return False

            try:
                # 1. Direct CDN-to-CDN transfer via Telegram
                payload = {'chat_id': chat_id, 'document': url, 'caption': caption}
                resp = requests.post(api_url, data=payload, timeout=45)
                data = resp.json()

                if data.get('ok'):
                    msg_id = data['result']['message_id']
                    self.log(f"[{bot_name}][{item_idx}/{total_items}] SUCCESS (Msg {msg_id}): {paper.get('exam')} {paper.get('year')} {paper.get('shift')}")
                    with self.lock:
                        if url not in self.progress['sent_urls']:
                            self.progress['sent_urls'].append(url)
                        if url in self.progress['failed']:
                            del self.progress['failed'][url]
                        self.save_progress()
                    return True

                # Rate limiting (429)
                if resp.status_code == 429 or data.get('error_code') == 429:
                    retry_after = data.get('parameters', {}).get('retry_after', 6)
                    self.log(f"[{bot_name}][{item_idx}/{total_items}] Rate limit (429). Sleeping {retry_after + 1}s...")
                    time.sleep(retry_after + 1)
                    continue

                err_desc = data.get('description', '')
                self.log(f"[{bot_name}][{item_idx}/{total_items}] TG API: {err_desc}")

                # Fallback: in-RAM stream directly to TG without disk write
                if "failed to get HTTP URL content" in err_desc or "wrong file identifier" in err_desc:
                    self.log(f"[{bot_name}][{item_idx}/{total_items}] Fallback in-RAM stream: {url.split('/')[-1]}")
                    raw_filename = urllib.parse.unquote(url.split('/')[-1])
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    dl_resp = requests.get(url, headers=headers, timeout=45)
                    if dl_resp.status_code == 200:
                        files = {'document': (raw_filename, dl_resp.content, 'application/pdf')}
                        s_resp = requests.post(api_url, data={'chat_id': chat_id, 'caption': caption}, files=files, timeout=60)
                        s_data = s_resp.json()
                        if s_data.get('ok'):
                            msg_id = s_data['result']['message_id']
                            self.log(f"[{bot_name}][{item_idx}/{total_items}] SUCCESS via stream (Msg {msg_id})")
                            with self.lock:
                                if url not in self.progress['sent_urls']:
                                    self.progress['sent_urls'].append(url)
                                if url in self.progress['failed']:
                                    del self.progress['failed'][url]
                                self.save_progress()
                            return True

            except Exception as e:
                self.log(f"[{bot_name}][{item_idx}/{total_items}] Exception attempt {attempt+1}: {e}")

            time.sleep(2)

        self.log(f"[{bot_name}][{item_idx}/{total_items}] FAILED: {paper.get('title')}")
        with self.lock:
            self.progress['failed'][url] = "Failed after retries"
            self.save_progress()
        return False

    def worker_loop(self, bot_idx, bot_token, chat_id, section_counts):
        while self.is_running:
            with self.lock:
                if not self.queue:
                    break
                item_idx, paper = self.queue.pop(0)
                self.current_item = paper

            sec = paper.get('section', paper.get('exam', 'General'))
            sec_count = section_counts.get(sec, 0)
            self.send_banner_if_needed(bot_token, sec, sec_count, chat_id)

            self.send_document(bot_idx, bot_token, chat_id, paper, item_idx, self.total_queued)
            time.sleep(1.8)

        if not self.queue:
            with self.lock:
                self.is_running = False
                self.log("🎉 All queued papers completed successfully!")

    def start_upload(self, items_to_send, bot_tokens, chat_id, section_counts):
        with self.lock:
            if self.is_running:
                return False
            self.is_running = True
            self.queue = list(items_to_send)
            self.total_queued = len(items_to_send)

        self.log(f"🚀 Started upload of {self.total_queued} papers using {len(bot_tokens)} bots...")

        self.worker_threads = []
        for i, token in enumerate(bot_tokens):
            t = threading.Thread(target=self.worker_loop, args=(i, token, chat_id, section_counts))
            t.daemon = True
            self.worker_threads.append(t)
            t.start()
        return True

    def stop_upload(self):
        with self.lock:
            self.is_running = False
            self.queue = []
        self.log("⏹️ Upload stopped by user.")

    def reset_progress(self):
        with self.lock:
            self.progress = {"sent_urls": [], "sent_sections": [], "failed": {}}
            self.save_progress()
        self.log("🔄 Progress history reset.")

# Instantiate Singleton
engine = UploadEngine()

# ----------------- Streamlit UI -----------------
st.title("🚆 RRB PYQ Telegram Cloud Uploader")
st.markdown("Automated **Dual-Bot CDN-to-CDN Transfer Engine** for Railway Previous Year Papers.")

# Sidebar Configuration
st.sidebar.header("⚙️ Bot & Channel Settings")

secret_token_1 = get_secret("BOT_TOKEN_1")
secret_token_2 = get_secret("BOT_TOKEN_2")

if secret_token_1:
    st.sidebar.success("✅ Bot 1 Token loaded from Secrets")
    bot_token_1 = secret_token_1
else:
    bot_token_1 = st.sidebar.text_input("Bot 1 Token", type="password", help="Enter Telegram Bot 1 Token")

if secret_token_2:
    st.sidebar.success("✅ Bot 2 Token loaded from Secrets")
    bot_token_2 = secret_token_2
else:
    bot_token_2 = st.sidebar.text_input("Bot 2 Token", type="password", help="Enter Telegram Bot 2 Token")

chat_id = st.sidebar.text_input("Telegram Channel ID / Username", value=DEFAULT_CHAT_ID, help="Channel username like @channel or ID like -100...")

st.sidebar.markdown("---")
st.sidebar.markdown("**💡 Streamlit Cloud Tip:**")
st.sidebar.caption("In Streamlit Community Cloud Settings -> Secrets, you can add:")
st.sidebar.code('BOT_TOKEN_1 = "..."\nBOT_TOKEN_2 = "..."', language="toml")

# Main Catalog
catalog = load_catalog()
available_exams = list(catalog.keys())

st.subheader("📚 Select Exams & Filters")
col1, col2 = st.columns([2, 1])

with col1:
    selected_exams = st.multiselect(
        "Choose Exams to Upload:",
        options=available_exams,
        default=["RRB Group D", "RRB ALP"] if available_exams else []
    )

with col2:
    lang_filter = st.selectbox(
        "Language Mode:",
        options=[
            "Hindi Medium (Recommended)",
            "All Available (Hindi + English)",
            "English Only"
        ]
    )

# Filter Logic
filtered_papers = []
section_counts = {}

for exam in selected_exams:
    exam_papers = catalog.get(exam, [])
    for p in exam_papers:
        lang = p.get('language', 'Standard').lower()
        if lang_filter == "Hindi Medium (Recommended)":
            if "english" in lang and "hindi" not in lang and "standard" not in lang:
                continue
        elif lang_filter == "English Only":
            if "hindi" in lang and "english" not in lang and "standard" not in lang:
                continue

        filtered_papers.append(p)
        sec = p.get('section', p.get('exam', 'General'))
        section_counts[sec] = section_counts.get(sec, 0) + 1

sent_urls_set = set(engine.progress.get('sent_urls', []))
pending_papers = [(idx, p) for idx, p in enumerate(filtered_papers, 1) if p['url'] not in sent_urls_set]
already_sent_count = len(filtered_papers) - len(pending_papers)

# Metrics Row
m1, m2, m3, m4 = st.columns(4)
m1.metric("Filtered Papers", len(filtered_papers))
m2.metric("Already Sent", already_sent_count)
m3.metric("Pending to Send", len(pending_papers))
m4.metric("Failed Count", len(engine.progress.get('failed', {})))

# Progress Bar
if len(filtered_papers) > 0:
    prog_pct = min(1.0, already_sent_count / len(filtered_papers))
    st.progress(prog_pct, text=f"Progress: {int(prog_pct * 100)}% ({already_sent_count}/{len(filtered_papers)} sent)")

# Controls Row
st.markdown("### 🎮 Controls")
c1, c2, c3, c4 = st.columns([1, 1, 1, 2])

valid_tokens = [t for t in [bot_token_1, bot_token_2] if t and len(t) > 20]

with c1:
    start_btn = st.button("🚀 Start Cloud Upload", type="primary", disabled=engine.is_running or not pending_papers or not valid_tokens)

with c2:
    stop_btn = st.button("⏹️ Stop / Pause", disabled=not engine.is_running)

with c3:
    if st.button("🔄 Refresh Status"):
        st.rerun()

with c4:
    if st.button("🗑️ Reset Progress (Clear Sent History)"):
        engine.reset_progress()
        st.success("History reset!")
        st.rerun()

if start_btn:
    if not valid_tokens:
        st.error("Please configure at least one valid Bot Token!")
    else:
        success = engine.start_upload(pending_papers, valid_tokens, chat_id, section_counts)
        if success:
            st.success(f"Upload initiated for {len(pending_papers)} papers!")
            st.rerun()

if stop_btn:
    engine.stop_upload()
    st.warning("Upload stopped.")
    st.rerun()

# Real-time Activity Log Box
st.markdown("### 📋 Real-Time Activity Log")
if engine.is_running:
    st.info("⚡ Background uploader is actively running in the cloud... (Auto-refreshing)")
    log_text = "\n".join(engine.logs[-30:])
    st.code(log_text if log_text else "Uploader initializing...", language="text")
    time.sleep(2)
    st.rerun()
else:
    log_text = "\n".join(engine.logs[-30:])
    st.code(log_text if log_text else "Engine idle. Select exams and click 'Start Cloud Upload'.", language="text")

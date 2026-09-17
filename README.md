# 🚆 RRB PYQ Telegram Cloud Uploader

An automated, cloud-hosted **Dual-Bot CDN-to-CDN Transfer Engine** built with Streamlit to upload all Railway Recruitment Board (RRB / RRC) Previous Year Question Papers directly to Telegram channels.

---

## 🌟 Key Features

- **24/7 Cloud Execution:** Deployed on Streamlit Community Cloud — runs independently in the cloud without keeping your mobile device or Termux awake.
- **Dual-Bot Concurrency:** Utilizes 2 Telegram bots simultaneously to maximize throughput while respecting Telegram flood/rate limits.
- **Zero Local Disk Usage (Direct CDN-to-CDN):** Streamed directly from official educational CDNs to Telegram servers via URL ingestion with in-RAM fallback.
- **1,295+ Structured Papers:**
  - **RRB NTPC** (Graduate & Undergraduate: 2016, 2017, 2021, 2022, 2025, 2026)
  - **RRB Group D (RRC Level 1)** (2018, 2019, 2022, 2025, 2026)
  - **RRB ALP** (CBT 1, CBT 2, CBAT Psycho: 2018, 2019, 2024, 2025, 2026)
  - **RRB Technician** (Grade 1 & Grade 3: 2018, 2024, 2025, 2026)
  - **RRB JE** (Junior Engineer CBT 1 & CBT 2: 2014, 2015, 2019, 2024, 2025)
  - **RPF Constable** (2019, 2025)
  - **RPF SI** (2019, 2024, 2025)
- **Organized Library Format:** Automatically posts Section Banners before every exam set and attaches structured metadata (Year, Stage, Shift, Date, Language) to every PDF.
- **Persistent State:** Saves progress in `upload_progress.json` so you can pause, resume, or restart anytime without duplicates.

---

## 🚀 How to Deploy on Streamlit Community Cloud (Step-by-Step)

### 1. Fork or Open Streamlit Community Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account (`mha93587-beep`).
2. Click **"New app"**.

### 2. Configure Deployment
- **Repository:** `mha93587-beep/rrb-pyq-telegram-uploader`
- **Branch:** `main`
- **Main file path:** `app.py`

### 3. Add Your Secrets (Crucial for Security)
Before clicking deploy, click **"Advanced settings..."** and paste your bot tokens in the **Secrets** box:

```toml
BOT_TOKEN_1 = "YOUR_FIRST_BOT_TOKEN"
BOT_TOKEN_2 = "YOUR_SECOND_BOT_TOKEN"
```

*(Note: Bot tokens are kept 100% secret and are never exposed in the public GitHub repo).*

### 4. Click "Deploy!"
Streamlit Cloud will automatically build and launch your web app in 1–2 minutes!

---

## 🎮 How to Use the Cloud App

1. Open your deployed Streamlit web URL.
2. Under **"Choose Exams to Upload"**, select any exam (e.g., RRB Group D, RRB ALP, RRB JE, etc.).
3. Choose your **Language Mode** (`Hindi Medium (Recommended)` or `All Available`).
4. Click **"🚀 Start Cloud Upload"**.
5. The cloud engine will start sending papers to the channel (`@rrballpyq`) in the background. You can safely close your browser or mobile phone!

---

## 🛠️ Local Development (Optional)

```bash
git clone https://github.com/mha93587-beep/rrb-pyq-telegram-uploader.git
cd rrb-pyq-telegram-uploader
pip install -r requirements.txt
streamlit run app.py
```

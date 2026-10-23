# 📈 Intelligence Filter - AI Stock Screener (Natural Language to SQL)

Intelligence Filter adalah aplikasi AI Stock Screener cerdas yang mengonversi bahasa alami (Natural Language) menjadi query SQL presisi untuk menyaring emiten saham berdasarkan metrik keuangan fundamental. Dibangun menggunakan arsitektur **Google Agent Development Kit (ADK)** dengan model LLM via OpenRouter.

🌐 **Live Demo URL**: [https://intelligence-filter-1098550132960.asia-southeast2.run.app](https://intelligence-filter-1098550132960.asia-southeast2.run.app)

---

## 🚀 Fitur Utama

1. **Dual Screening Mode**:
   - **One-Shot**: Konversi cepat pertanyaan langsung menjadi query SQL SELECT tunggal yang siap dieksekusi dalam 1 langkah.
   - **Multistep (Google ADK Autonomous Agent)**: Agen otonom multi-langkah yang menganalisis kriteria pengguna, memeriksa statistik metrik pasar (`get_column_stats`), mengeksekusi query SQL (`run_sql`), dan menghasilkan **Executive Summary** terstruktur secara *streaming token-by-token*.
2. **Real-time Reasoning & Execution Timeline**:
   - Visualisasi transparan setiap tahapan pemikiran agen, tool calls, SQL executed, dan validasi data secara langsung via Server-Sent Events (SSE).
3. **Interactive & Responsive Modern UI**:
   - Dashboard analitik saham modern dengan tema dark mode, visualisasi tabel interaktif, export CSV/JSON, preset query siap pakai, dan salin SQL dalam satu klik.
4. **Keamanan & Guardrails**:
   - Read-only SQLite execution: hanya menerima query `SELECT`. Query `DROP`, `DELETE`, `INSERT`, `UPDATE`, dsb. diblokir secara ketat di layer database engine.

---

## 🏗️ Arsitektur & Teknologi

- **Backend**: FastAPI & Uvicorn (Python 3.11)
- **AI Agent Framework**: [Google Agent Development Kit (ADK)](https://github.com/google/agent-development-kit) (`LlmAgent`, `InMemoryRunner`, `LiteLlm` model adapter)
- **Database**: SQLite3 (dataset 32 emiten saham dengan 8 rasio/metrik fundamental)
- **Frontend**: Vanilla HTML5, CSS3 Glassmorphism UI, SSE Client, marked.js
- **Cloud Infrastructure**: Google Cloud Run (Fully managed, auto-scaling 0-2 instance, spec efisien)

---

## 📊 Skema Database (`stocks`)

| Kolom | Tipe | Deskripsi & Interpretasi |
|---|---|---|
| `symbol` | TEXT | Kode ticker saham (contoh: PSAB, SIDO, SMSM, dll.) |
| `current_ratio` | REAL | Rasio lancar / likuiditas (> 1.5 dianggap likuid) |
| `der` | REAL | Debt-to-Equity Ratio (< 0.5 atau < 1 utang aman) |
| `dividend_yield` | REAL | Yield dividen dalam persen (> 7% dividen tinggi) |
| `fcf_ttm` | REAL | Free Cash Flow 12 bulan terakhir (Rupiah) |
| `gross_margin` | REAL | Margin laba kotor dalam persen |
| `net_profit_ttm` | REAL | Laba bersih 12 bulan terakhir (Rupiah) |
| `roe_ttm` | REAL | Return on Equity dalam persen (> 15% profitable) |

---

## 🛠️ Menjalankan Secara Lokal

### 1. Prasyarat
- Python 3.10+
- OpenRouter API Key (bisa didapatkan di [openrouter.ai](https://openrouter.ai))

### 2. Instalasi & Setup
```bash
# Clone repositori
git clone https://github.com/MMumtazSakho/intelligence-filter.git
cd intelligence-filter

# Buat virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependensi
pip install -r requirements.txt

# Buat file .env dan tambahkan API Key
echo "OPENROUTER_API_KEY=sk-or-v1-YOUR_KEY_HERE" > .env

# Inisialisasi database SQLite
python db.py

# Jalankan server
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Akses aplikasi di browser pada: `http://localhost:8000`

---

## ☁️ Deployment ke Google Cloud Run

Deploy aplikasi langsung menggunakan Google Cloud SDK:

```bash
gcloud run deploy intelligence-filter \
  --project=id-rd-ai-demo \
  --region=asia-southeast2 \
  --source=. \
  --min-instances=0 \
  --max-instances=2 \
  --cpu=1 \
  --memory=1Gi \
  --allow-unauthenticated \
  --timeout=300 \
  --set-env-vars=OPENROUTER_API_KEY="sk-or-v1-YOUR_KEY_HERE"
```

---

## 📄 Lisensi
MIT License.

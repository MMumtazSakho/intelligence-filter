import os
import json
import re
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Ensure mcp and mcp_types compatibility for litellm under google-adk
try:
    import mcp.types
    for _name in ["CacheableResult", "InputRequiredResult"]:
        if not hasattr(mcp.types, _name):
            setattr(mcp.types, _name, type(_name, (), {}))
except Exception:
    pass

try:
    import mcp_types
    for _name in ["CacheableResult", "InputRequiredResult"]:
        if not hasattr(mcp_types, _name):
            setattr(mcp_types, _name, type(_name, (), {}))
except Exception:
    pass

# Google ADK Framework Imports
from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types

from db import SCHEMA_DESCRIPTION, execute_safe_query, DB_PATH
import sqlite3

# Load environment variables
load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL_NAME = "openai/openai/gpt-6-luna"
APP_NAME = "google_adk_stock_screener"

def get_adk_model() -> LiteLlm:
    """Returns Google ADK LiteLlm adapter for OpenRouter DeepSeek v4.1 Flash."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not set in .env")
    return LiteLlm(
        model=MODEL_NAME,
        api_base=OPENROUTER_BASE_URL,
        api_key=api_key,
    )

def extract_sql_from_text(text: str) -> str:
    """Extract clean SQL query from text."""
    sql_match = re.search(r"```(?:sql)?\s*(SELECT.*?)```", text, re.DOTALL | re.IGNORECASE)
    if sql_match:
        return sql_match.group(1).strip()
    
    select_match = re.search(r"(SELECT\s+.*)", text, re.DOTALL | re.IGNORECASE)
    if select_match:
        cand = select_match.group(1).strip()
        cand = re.sub(r"```.*$", "", cand, flags=re.DOTALL).strip()
        if ";" in cand:
            cand = cand.split(";")[0] + ";"
        return cand.strip()
    
    return text.strip()

# -------------------------------------------------------------
# GOOGLE ADK TOOLS DEFINITION
# -------------------------------------------------------------
class StockScreenerContext:
    def __init__(self):
        self.executed_sqls: List[str] = []
        self.executed_infos: List[str] = []
        self.captured_results: List[Dict[str, Any]] = []

def create_adk_tools(ctx: StockScreenerContext):
    def run_sql(query: str, info: str) -> str:
        """Menjalankan query SQL SELECT pada database SQLite tabel stocks dan mengembalikan data emiten.

        Args:
            query: Query SQL SELECT yang valid untuk dijalankan pada tabel stocks.
            info: Penjelasan singkat dalam bahasa manusia tentang apa yang dilakukan oleh query ini (tujuan filter, kriteria rasio yang digunakan, dan urutan hasil) untuk menginformasikan kepada user.
        """
        clean_q = query.strip()
        clean_info = (info or "").strip()
        ctx.executed_sqls.append(clean_q)
        ctx.executed_infos.append(clean_info)
        rows, err = execute_safe_query(clean_q)
        if err:
            return json.dumps({"status": "error", "message": err, "info": clean_info})
        ctx.captured_results = rows
        return json.dumps({
            "status": "success",
            "info": clean_info,
            "total_matches": len(rows),
            "sample_stocks": rows[:8]
        })

    def get_column_stats(column_name: str) -> str:
        """Mendapatkan statistik pasar (min, avg, max) untuk kolom tertentu pada tabel stocks."""
        allowed_cols = ["current_ratio", "der", "dividend_yield", "fcf_ttm", "gross_margin", "net_profit_ttm", "roe_ttm"]
        if column_name not in allowed_cols:
            return json.dumps({"error": f"Kolom tidak valid. Pilihan: {allowed_cols}"})
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT MIN({column_name}), AVG({column_name}), MAX({column_name}) FROM stocks")
            row = cursor.fetchone()
            stats = {
                "column": column_name,
                "min": round(row[0], 2) if row[0] is not None else None,
                "avg": round(row[1], 2) if row[1] is not None else None,
                "max": round(row[2], 2) if row[2] is not None else None,
            }
            return json.dumps(stats)

    return run_sql, get_column_stats

# -------------------------------------------------------------
# MODE 1: ONE-SHOT (Google ADK LlmAgent)
# -------------------------------------------------------------
def run_oneshot_screening(user_prompt: str) -> Dict[str, Any]:
    """
    Mode One-Shot menggunakan Google ADK LlmAgent untuk menghasilkan SQL dalam 1 langkah.
    """
    ctx = StockScreenerContext()
    run_sql_tool, _ = create_adk_tools(ctx)

    agent = LlmAgent(
        name="OneShotScreener",
        model=get_adk_model(),
        instruction=f"""Anda adalah AI Stock Screener SQL Generator menggunakan Google ADK.
Tugas Anda adalah langsung mengubah permintaan pengguna menjadi SQL SELECT yang valid dan mengeksekusinya via run_sql.
Query SQL yang Anda jalankan melalui `run_sql` WAJIB merupakan representasi akurat yang langsung menjawab pertanyaan/kriteria screening pengguna.
Saat memanggil run_sql, WAJIB sertakan:
- query: Query SQL SELECT yang valid.
- info: Penjelasan singkat dalam bahasa Indonesia kepada user mengenai apa yang dilakukan query tersebut (tujuan filter kriteria saham dan urutannya).
{SCHEMA_DESCRIPTION}
Aturan: Hanya boleh SELECT. Format persentase disimpan sebagai angka persen (misal 8 untuk 8%).""",
        tools=[run_sql_tool]
    )

    runner = InMemoryRunner(app_name=APP_NAME, agent=agent)
    session_id = f"oneshot-{uuid.uuid4().hex[:8]}"
    user_id = "user-oneshot"

    asyncio.run(runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id
    ))

    events = list(runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"Screen saham berikut dengan SQL: {user_prompt}")]
        )
    ))

    final_sql = ctx.executed_sqls[-1] if ctx.executed_sqls else ""
    final_info = ctx.executed_infos[-1] if ctx.executed_infos else ""
    results = ctx.captured_results

    if not final_sql:
        # Fallback: check if text response contained SQL
        for e in events:
            if hasattr(e, "content") and e.content:
                for p in e.content.parts:
                    if getattr(p, "text", None):
                        cand = extract_sql_from_text(p.text)
                        if cand.upper().startswith("SELECT"):
                            final_sql = cand
                            results, _ = execute_safe_query(final_sql)
                            break

    return {
        "mode": "one-shot",
        "prompt": user_prompt,
        "sql": final_sql or "SELECT * FROM stocks;",
        "info": final_info,
        "results": results,
        "total_results": len(results)
    }

# -------------------------------------------------------------
# MODE 2: MULTISTEP (Google ADK Multi-step Agent & Real-time Trace)
# -------------------------------------------------------------
def run_multistep_screening(user_prompt: str) -> Dict[str, Any]:
    """
    Mode Multistep menggunakan Google ADK LlmAgent dengan multi-turn reasoning dan executive summary.
    """
    ctx = StockScreenerContext()
    run_sql_tool, get_stats_tool = create_adk_tools(ctx)

    agent = LlmAgent(
        name="MultistepScreener",
        model=get_adk_model(),
        instruction=f"""Anda adalah Senior Equity Research Analyst & Quantitative Screener Agent berbasis Google ADK.
Tugas Anda:
1. Menganalisis kriteria screening dari pengguna.
2. Gunakan `get_column_stats` jika perlu mengetahui rata-rata distribusi rasio di pasar.
3. Gunakan `run_sql` untuk mengeksekusi query SQLite pada tabel stocks. Saat memanggil `run_sql`, WAJIB sertakan parameter `query` dan `info` (penjelasan singkat bahasa manusia tentang apa yang dilakukan query tersebut, kriteria filter, dan tujuan penyaringan untuk user).
4. ATURAN UTAMA QUERY SQL: Query SQL terakhir yang Anda panggil melalui `run_sql` WAJIB merupakan representasi final dari jawaban atas pertanyaan/kriteria screening pengguna. Hasil tabel data yang ditampilkan kepada pengguna di aplikasi diambil langsung dari hasil query SQL terakhir ini. Jangan menjalankan query tambahan setelah query jawaban final tersebut.
5. Tuliskan Executive Summary komprehensif untuk investor (Saham Terpilih, Kekuatan Finansial, Catatan Risiko, dan Rekomendasi).
{SCHEMA_DESCRIPTION}""",
        tools=[run_sql_tool, get_stats_tool]
    )

    runner = InMemoryRunner(app_name=APP_NAME, agent=agent)
    session_id = f"multistep-{uuid.uuid4().hex[:8]}"
    user_id = "user-multistep"

    asyncio.run(runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id
    ))

    events = list(runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"Analisis dan carikan saham sesuai kriteria berikut: {user_prompt}. Pastikan eksekusi run_sql terakhir adalah query final yang merepresentasikan jawaban dari kriteria ini.")]
        )
    ))

    summary_text = ""
    for e in events:
        if hasattr(e, "content") and e.content:
            for p in e.content.parts:
                if getattr(p, "text", None):
                    summary_text += p.text

    final_sql = ctx.executed_sqls[-1] if ctx.executed_sqls else "SELECT * FROM stocks;"
    final_info = ctx.executed_infos[-1] if ctx.executed_infos else ""
    results = ctx.captured_results
    if not results and final_sql:
        results, _ = execute_safe_query(final_sql)

    return {
        "mode": "multistep",
        "prompt": user_prompt,
        "sql": final_sql,
        "info": final_info,
        "all_queries": ctx.executed_sqls,
        "results": results,
        "summary": summary_text,
        "total_results": len(results)
    }

def run_multistep_screening_stream(user_prompt: str):
    """
    Generator streaming Google ADK events secara real-time ke web UI.
    """
    ctx = StockScreenerContext()
    run_sql_tool, get_stats_tool = create_adk_tools(ctx)

    agent = LlmAgent(
        name="MultistepScreener",
        model=get_adk_model(),
        instruction=f"""Anda adalah Senior Equity Research Analyst & Quantitative Screener Agent berbasis Google ADK.
Tugas Anda:
1. Menganalisis kriteria screening dari pengguna.
2. Gunakan `get_column_stats` jika perlu mengetahui rata-rata distribusi rasio di pasar.
3. Gunakan `run_sql` untuk mengeksekusi query SQLite pada tabel stocks. Saat memanggil `run_sql`, WAJIB sertakan parameter `query` dan `info` (penjelasan singkat bahasa manusia tentang apa yang dilakukan query tersebut, kriteria filter, dan tujuan penyaringan untuk user).
4. ATURAN UTAMA QUERY SQL: Query SQL terakhir yang Anda panggil melalui `run_sql` WAJIB merupakan representasi final dari jawaban atas pertanyaan/kriteria screening pengguna. Hasil tabel data yang ditampilkan kepada pengguna di aplikasi diambil langsung dari hasil query SQL terakhir ini. Jangan menjalankan query tambahan setelah query jawaban final tersebut.
5. Tuliskan Executive Summary komprehensif untuk investor (Saham Terpilih, Kekuatan Finansial, Catatan Risiko, dan Rekomendasi).
{SCHEMA_DESCRIPTION}""",
        tools=[run_sql_tool, get_stats_tool]
    )

    runner = InMemoryRunner(app_name=APP_NAME, agent=agent)
    session_id = f"stream-{uuid.uuid4().hex[:8]}"
    user_id = "user-stream"

    asyncio.run(runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id
    ))

    summary_accumulated = ""
    summary_started = False
    run_config = RunConfig(streaming_mode=StreamingMode.SSE)

    yield {"type": "step_start", "info": "Menganalisis kriteria pencarian"}

    for event in runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"Analisis dan carikan saham sesuai kriteria berikut: {user_prompt}. Pastikan eksekusi run_sql terakhir adalah query final yang merepresentasikan jawaban dari kriteria ini.")]
        ),
        run_config=run_config
    ):
        partial = bool(getattr(event, "partial", False))
        content = getattr(event, "content", None)
        if not content:
            continue

        for part in getattr(content, "parts", []):
            # Check function call (tool invocation)
            fn_call = getattr(part, "function_call", None)
            if fn_call and not partial:
                tool_name = getattr(fn_call, "name", "tool")
                tool_args = getattr(fn_call, "args", {}) or {}

                if tool_name == "run_sql":
                    query_info = (tool_args.get("info") or "").strip() or "Menjalankan query ke database"
                    yield {"type": "step_start", "info": query_info}
                elif tool_name == "get_column_stats":
                    col = tool_args.get("column_name", "")
                    yield {"type": "step_start", "info": f"Memeriksa distribusi {col} di pasar"}

            # Check function response (tool result)
            fn_resp = getattr(part, "function_response", None)
            if fn_resp:
                tool_name = getattr(fn_resp, "name", "")
                payload = getattr(fn_resp, "response", {}) or {}
                if isinstance(payload, dict) and "result" in payload and isinstance(payload["result"], str):
                    payload = payload["result"]
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        payload = {}

                meta = ""
                if tool_name == "run_sql":
                    if isinstance(payload, dict) and payload.get("status") == "error":
                        meta = f"Gagal: {payload.get('message', '')}"
                    else:
                        meta = f"{len(ctx.captured_results)} emiten ditemukan"
                elif tool_name == "get_column_stats" and isinstance(payload, dict):
                    meta = f"min {payload.get('min')} · rata-rata {payload.get('avg')} · maks {payload.get('max')}"
                yield {"type": "step_end", "meta": meta}

            # Check text generation (Summary streaming tokens)
            text = getattr(part, "text", None)
            if text:
                if not summary_started:
                    summary_started = True
                    yield {"type": "step_start", "info": "Menyusun ringkasan"}
                if partial:
                    summary_accumulated += text
                    yield {
                        "type": "summary_chunk",
                        "chunk": text
                    }
                elif not summary_accumulated:
                    summary_accumulated = text
                    yield {
                        "type": "summary_chunk",
                        "chunk": text
                    }

    final_sql = ctx.executed_sqls[-1] if ctx.executed_sqls else "SELECT * FROM stocks;"
    final_info = ctx.executed_infos[-1] if ctx.executed_infos else ""
    results = ctx.captured_results
    if not results and final_sql:
        results, _ = execute_safe_query(final_sql)

    yield {
        "type": "complete",
        "sql": final_sql,
        "info": final_info,
        "results": results,
        "summary": summary_accumulated,
        "total_results": len(results)
    }

if __name__ == "__main__":
    print("Testing Google ADK One-Shot...")
    res = run_oneshot_screening("Saham dengan dividen yield di atas 8 persen dan DER di bawah 0.5")
    print("SQL:", res["sql"])
    print("Total:", res["total_results"])

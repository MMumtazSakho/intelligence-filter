import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from db import init_db, get_all_stocks, execute_safe_query
from agent import run_oneshot_screening, run_multistep_screening, run_multistep_screening_stream

# Initialize database on startup
init_db()

app = FastAPI(title="AI-Powered Stock Screener", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static"):
        response.headers["Cache-Control"] = "no-store"
    return response

class ScreenRequest(BaseModel):
    prompt: str
    mode: Optional[str] = "one-shot"

class ExecuteSqlRequest(BaseModel):
    sql: str

@app.get("/api/stocks")
def api_get_stocks():
    """Returns all 32 stocks from database."""
    stocks = get_all_stocks()
    return {"status": "success", "total": len(stocks), "data": stocks}

@app.post("/api/screen")
def api_screen_stocks(req: ScreenRequest):
    """
    Screens stocks using Natural Language to SQL.
    Supports 'one-shot' and 'multistep' modes.
    """
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    try:
        if req.mode == "multistep":
            result = run_multistep_screening(prompt)
        else:
            result = run_oneshot_screening(prompt)
        
        return {"status": "success", **result}
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "mode": req.mode,
            "prompt": prompt,
            "results": [],
            "sql": ""
        }

@app.post("/api/screen-stream")
def api_screen_stream(req: ScreenRequest):
    """
    Real-time streaming SSE endpoint for step-by-step Agent reasoning & tool calls.
    """
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    def event_generator():
        import json
        try:
            for event in run_multistep_screening_stream(prompt):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/execute-sql")
def api_execute_sql(req: ExecuteSqlRequest):
    """Allows user to edit and execute SQL query directly."""
    sql = req.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="SQL query cannot be empty.")
    
    rows, err = execute_safe_query(sql)
    return {
        "status": "error" if err else "success",
        "sql": sql,
        "results": rows,
        "error": err,
        "total_results": len(rows)
    }

# Serve static directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "AI Stock Screener API is running. Place static/index.html to view UI."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from dotenv import load_dotenv

from instagram_fetcher import fetch_profile, login, is_logged_in
from analyzer import analyze_and_recommend

load_dotenv()

app = FastAPI(title="InstaScope API")

FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    username: str
    max_posts: int = 30


class LoginRequest(BaseModel):
    username: str
    password: str


@app.get("/ui")
def serve_ui():
    return FileResponse(os.path.abspath(FRONTEND_PATH))


@app.get("/health")
def health():
    return {"status": "ok", "ig_logged_in": is_logged_in()}


@app.post("/api/login")
def ig_login(req: LoginRequest):
    try:
        login(req.username, req.password)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Instagram login failed: {str(e)}")


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    username = req.username.lstrip("@").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    try:
        profile = fetch_profile(username, max_posts=min(req.max_posts, 50))
    except Exception as e:
        msg = str(e)
        if "404" in msg or "does not exist" in msg.lower():
            raise HTTPException(status_code=404, detail=f"Instagram profile '@{username}' not found or is private")
        raise HTTPException(status_code=502, detail=f"Failed to fetch Instagram data: {msg}")

    try:
        result = analyze_and_recommend(profile, api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    return result

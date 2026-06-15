import os
import re
import json
import time
import uuid
import sqlite3
import threading
from flask import Flask, render_template, request, jsonify, redirect, Response
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from demo_routes import demo_bp
from scraper import scrape_profile
from analyzer import analyze_profile, analyze_overview, analyze_deep, chat_with_context

app = Flask(__name__)
CORS(app)
app.register_blueprint(demo_bp)

# In-memory store for chat context (keyed by username)
_analysis_cache: dict = {}

# ──────────────────────────────────────────────────────────────
# Async job store — SQLite on the instance filesystem so it is
# shared across all Gunicorn workers (in-memory dicts are not).
# ──────────────────────────────────────────────────────────────
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.db")


def _db():
    conn = sqlite3.connect(_DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def _init_jobs_db():
    with _db() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS jobs "
            "(id TEXT PRIMARY KEY, status TEXT, data TEXT, error TEXT, updated REAL)"
        )


_init_jobs_db()


def _job_set(job_id, status, data=None, error=None):
    with _db() as c:
        c.execute(
            "INSERT INTO jobs(id, status, data, error, updated) VALUES(?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET status=excluded.status, "
            "data=COALESCE(excluded.data, jobs.data), "
            "error=excluded.error, updated=excluded.updated",
            (job_id, status, json.dumps(data) if data is not None else None, error, time.time()),
        )


def _job_get(job_id):
    with _db() as c:
        row = c.execute(
            "SELECT status, data, error FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
    if not row:
        return None
    return {
        "status": row[0],
        "data": json.loads(row[1]) if row[1] else None,
        "error": row[2],
    }


def _profile_to_dict(profile):
    return {
        "username": profile.username,
        "full_name": profile.full_name,
        "followers": profile.followers,
        "following": profile.following,
        "posts_count": profile.posts_count,
        "bio": profile.bio,
        "category": profile.category,
        "profile_pic_url": profile.profile_pic_url,
        "avg_engagement_rate": profile.avg_engagement_rate,
        "posting_frequency_per_week": profile.posting_frequency_per_week,
        "best_posting_days": profile.best_posting_days,
        "engagement_trend": profile.engagement_trend,
        "top_format": profile.top_format,
        "avg_reel_views": profile.meta.get("avg_reel_views", 0),
        "posts_scraped": profile.meta.get("posts_scraped", 0),
    }


def _run_analysis_job(job_id, username, api_key, apify_token):
    """Background worker: scrape → fast overview → deep modules, writing
    progress to SQLite at each stage so the client can render progressively."""
    try:
        _job_set(job_id, "scraping")
        try:
            profile = scrape_profile(username, apify_token)
        except Exception as e:
            _job_set(job_id, "error", error=f"Scraping failed: {e}")
            return
        profile_dict = _profile_to_dict(profile)

        _job_set(job_id, "analyzing_overview")
        overview = analyze_overview(profile, api_key)
        if not overview.get("ok"):
            _job_set(job_id, "error", error=overview.get("error", "Overview analysis failed"))
            return
        overview["profile"] = profile_dict
        _job_set(job_id, "overview_ready", data=overview)

        # Deep modules — runs in this thread, free of any request timeout.
        deep = analyze_deep(profile, api_key, overview=overview)
        merged = dict(overview)
        if deep.get("ok"):
            for k, v in deep.items():
                if k != "ok":
                    merged[k] = v
        merged["profile"] = profile_dict
        merged["deep_ok"] = bool(deep.get("ok"))
        _analysis_cache[username.lower()] = merged
        _job_set(job_id, "complete", data=merged)
    except Exception as e:
        _job_set(job_id, "error", error=str(e))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "api_key_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        "apify_configured": bool(os.getenv("APIFY_API_TOKEN")),
    })


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").lstrip("@").strip()
    if not username:
        return jsonify({"ok": False, "error": "Username is required"}), 400

    api_key = data.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
    apify_token = os.getenv("APIFY_API_TOKEN")

    try:
        profile = scrape_profile(username, apify_token)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Scraping failed: {e}"}), 500

    result = analyze_profile(profile, api_key)
    if not result.get("ok"):
        return jsonify(result), 500

    result["profile"] = {
        "username": profile.username,
        "full_name": profile.full_name,
        "followers": profile.followers,
        "following": profile.following,
        "posts_count": profile.posts_count,
        "bio": profile.bio,
        "category": profile.category,
        "profile_pic_url": profile.profile_pic_url,
        "avg_engagement_rate": profile.avg_engagement_rate,
        "posting_frequency_per_week": profile.posting_frequency_per_week,
        "best_posting_days": profile.best_posting_days,
        "engagement_trend": profile.engagement_trend,
        "top_format": profile.top_format,
        "avg_reel_views": profile.meta.get("avg_reel_views", 0),
        "posts_scraped": profile.meta.get("posts_scraped", 0),
    }

    _analysis_cache[username.lower()] = result
    return jsonify(result)


@app.route("/api/analyze/start", methods=["POST"])
def analyze_start():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").lstrip("@").strip()
    if not username:
        return jsonify({"ok": False, "error": "Username is required"}), 400

    api_key = data.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
    apify_token = os.getenv("APIFY_API_TOKEN")

    job_id = uuid.uuid4().hex
    _job_set(job_id, "queued")
    threading.Thread(
        target=_run_analysis_job,
        args=(job_id, username, api_key, apify_token),
        daemon=True,
    ).start()
    return jsonify({"ok": True, "job_id": job_id})


@app.route("/api/analyze/status/<job_id>")
def analyze_status(job_id):
    job = _job_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    return jsonify({"ok": True, **job})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").lstrip("@").lower().strip()
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"ok": False, "error": "Message required"}), 400

    analysis = _analysis_cache.get(username) or data.get("analysis") or {}
    reply = chat_with_context(username, analysis, message)
    return jsonify({"ok": True, "reply": reply})


def _resolve_analysis():
    """Prefer the analysis sent by the client (works across Gunicorn workers
    and instance restarts); fall back to the in-memory server cache."""
    body = request.get_json(silent=True) or {}
    username = (request.args.get("username") or body.get("username") or "").lstrip("@").lower().strip()
    source = body.get("analysis") or _analysis_cache.get(username, {})
    return source


@app.route("/api/analytics/benchmarks", methods=["GET", "POST"])
def benchmarks():
    source = _resolve_analysis()
    analytics = source.get("analytics", {}) if source else {}
    profile = source.get("profile", {}) if source else {}
    has_data = bool(analytics)

    er_str = analytics.get("avg_engagement_rate", "3.2%")
    try:
        er_val = float(str(er_str).replace("%", "").strip())
    except Exception:
        er_val = 3.2

    freq = analytics.get("posting_frequency_per_week", "3x / week")
    try:
        freq_val = float(str(freq).replace("x / week", "").replace("x/week", "").replace("/ week", "").replace("x", "").strip())
    except Exception:
        freq_val = 3.0

    # Real avg reel views from the scrape; format large counts as M, else K.
    avg_views_raw = profile.get("avg_reel_views", 0) or 0
    if avg_views_raw >= 1_000_000:
        views_val, views_unit = round(avg_views_raw / 1_000_000, 1), "M"
    elif avg_views_raw:
        views_val, views_unit = round(avg_views_raw / 1000), "K"
    else:
        views_val, views_unit = 24, "K"
    views_ahead = avg_views_raw >= 85_000

    metrics = [
        {
            "label": "Engagement Rate",
            "user_value": er_val,
            "top_value": 8.5,
            "unit": "%",
            "verdict": "Ahead" if er_val >= 6 else "Close" if er_val >= 3 else "Behind",
        },
        {
            "label": "Post Frequency",
            "user_value": freq_val,
            "top_value": 7,
            "unit": "x/wk",
            "verdict": "Ahead" if freq_val >= 6 else "Close" if freq_val >= 3 else "Behind",
        },
        {
            "label": "Avg Views / Reel",
            "user_value": views_val,
            "top_value": 85,
            "unit": views_unit,
            "verdict": "Ahead" if views_ahead else "Close" if avg_views_raw >= 40_000 else "Behind",
        },
    ]
    return jsonify({
        "ok": True,
        "has_data": has_data,
        "metrics": metrics,
        "motivational": "You're <strong>in the top 30%</strong> for engagement in your niche. Increase posting frequency to unlock the next growth tier.",
    })


@app.route("/api/recommendations", methods=["GET", "POST"])
def recommendations():
    cached = _resolve_analysis()
    nbp = cached.get("next_best_post", {})
    analytics = cached.get("analytics", {})
    top_tactics = cached.get("top_tactics", [])

    best_day = nbp.get("best_day") or (analytics.get("best_posting_days") or [None])[0]
    best_time = nbp.get("best_time")
    top_format = analytics.get("top_format", "Reels")

    recs = []

    # Timing rec — derived from the real analysis best day/time
    if best_day and best_time:
        recs.append({
            "type": "timing",
            "type_color": "#34d399",
            "headline": f"Post {best_day} at {best_time} for peak reach",
            "body": f"Your audience engagement peaks on {best_day}. Scheduling posts in this window aligns with your account's strongest performance pattern.",
            "stat": "Peak engagement window",
            "confidence": 4,
            "next_preview": "Next: Content tactic",
        })

    # Tactic recs — pulled straight from the AI growth report
    colors = ["#fbbf24", "#818cf8", "#34d399"]
    for i, t in enumerate(top_tactics[:2]):
        recs.append({
            "type": "content",
            "type_color": colors[i % len(colors)],
            "headline": t.get("name", "Growth tactic"),
            "body": t.get("impact", ""),
            "stat": t.get("difficulty", "") + (" · " + t.get("time_to_implement", "") if t.get("time_to_implement") else ""),
            "confidence": 4,
            "next_preview": "Next: Format strategy",
        })

    # Format rec — based on the account's actual top format
    recs.append({
        "type": "format",
        "type_color": "#818cf8",
        "headline": f"Lean into {top_format} — your top-performing format",
        "body": f"{top_format} drive the most engagement on your account right now. Prioritize this format to maximize organic reach.",
        "stat": "Top format",
        "confidence": 4,
        "next_preview": "Next: Keep posting consistently",
    })

    # Fallback if no analysis cached yet
    if not recs or (not best_day and not top_tactics):
        recs = [{
            "type": "content",
            "type_color": "#fbbf24",
            "headline": "Run an analysis to unlock tailored recommendations",
            "body": "Personalized timing, content, and format tips appear here after your account is analyzed.",
            "stat": "",
            "confidence": 3,
            "next_preview": "",
        }]

    return jsonify({"ok": True, "recommendations": recs})


@app.route("/api/email/preview/<user_id>")
def email_preview(user_id):
    html = _build_email_html(user_id)
    plain = _build_email_plain(user_id)
    return jsonify({
        "ok": True,
        "html": html,
        "text": plain,
        "recipient_email": f"{user_id}@example.com",
    })


def _build_email_html(username: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>CreatorOS Weekly Digest</title></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:32px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px;">
  <tr><td style="background:linear-gradient(135deg,#4338ca,#0d9488);padding:32px 40px;">
    <p style="margin:0;color:#a5b4fc;font-size:12px;letter-spacing:2px;text-transform:uppercase;">CreatorOS Weekly Digest</p>
    <h1 style="margin:8px 0 0;color:#ffffff;font-size:28px;">Your Growth Report</h1>
    <p style="margin:6px 0 0;color:#c7d2fe;font-size:14px;">Week of June 10, 2026 &middot; @{username}</p>
  </td></tr>
  <tr><td style="padding:32px 40px 0;">
    <p style="margin:0 0 12px;color:#6366f1;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">Top Recommendation</p>
    <h2 style="margin:0 0 10px;color:#111827;font-size:20px;">Post on Tuesday at 7 PM</h2>
    <p style="margin:0;color:#4b5563;font-size:15px;line-height:1.6;">Your audience engagement peaks Tuesday evenings. Shifting 2 posts per week to this window could increase your reach by 40%.</p>
    <table style="margin-top:16px;"><tr><td style="background:#ede9fe;border-radius:6px;padding:8px 16px;color:#4338ca;font-size:13px;font-weight:700;">40% reach increase</td></tr></table>
  </td></tr>
  <tr><td style="padding:24px 40px 0;">
    <hr style="border:none;border-top:1px solid #e5e7eb;margin-bottom:24px;">
    <p style="margin:0 0 12px;color:#059669;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">Best Post This Week</p>
    <h2 style="margin:0 0 10px;color:#111827;font-size:18px;">Behind-the-Scenes Process Video</h2>
    <p style="margin:0;color:#4b5563;font-size:15px;line-height:1.6;font-style:italic;">"Nobody shows what this actually looks like..."</p>
    <p style="margin:12px 0 0;color:#6b7280;font-size:14px;">Predicted reach: 28K&ndash;52K &middot; Format: Reel &middot; Best time: Tuesday 7 PM</p>
  </td></tr>
  <tr><td style="padding:24px 40px 0;">
    <hr style="border:none;border-top:1px solid #e5e7eb;margin-bottom:24px;">
    <table width="100%" style="background:#fffbeb;border-left:4px solid #f59e0b;padding:16px 20px;"><tr><td>
      <p style="margin:0 0 6px;color:#b45309;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">🔥 Trend Alert</p>
      <p style="margin:0;color:#78350f;font-size:15px;font-weight:600;">Day-in-the-life content is surging in your niche</p>
      <p style="margin:6px 0 0;color:#92400e;font-size:13px;">This format is getting 3&times; the shares of standard tutorial content this week.</p>
    </td></tr></table>
  </td></tr>
  <tr><td style="padding:32px 40px;" align="center">
    <a href="#" style="background:linear-gradient(135deg,#4338ca,#0d9488);color:#ffffff;text-decoration:none;padding:14px 32px;border-radius:8px;font-size:15px;font-weight:700;display:inline-block;">View Full Growth Report &rarr;</a>
  </td></tr>
  <tr><td style="background:#f9fafb;padding:20px 40px;border-top:1px solid #e5e7eb;">
    <p style="margin:0;color:#9ca3af;font-size:12px;text-align:center;">Sent every Monday at 8:00 AM &middot; <a href="#" style="color:#6366f1;">Unsubscribe</a> &middot; CreatorOS</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""


def _build_email_plain(username: str) -> str:
    return f"""CreatorOS Weekly Digest
Week of June 10, 2026 - @{username}

TOP RECOMMENDATION
Post on Tuesday at 7 PM
Your audience engagement peaks Tuesday evenings. Shifting 2 posts/week could increase reach by 40%.

BEST POST THIS WEEK
Behind-the-Scenes Process Video
Hook: "Nobody shows what this actually looks like..."
Predicted reach: 28K-52K | Format: Reel | Best time: Tue 7 PM

TREND ALERT
Day-in-the-life content is surging in your niche.
This format is getting 3x the shares of standard tutorial content this week.

View your full growth report at creatorOS.app

---
Sent every Monday at 8:00 AM | CreatorOS
"""


# ──────────────────────────────────────────────────────────────
# SEO / crawler endpoints
# ──────────────────────────────────────────────────────────────
SITE_URL = os.getenv("SITE_URL", "https://creatoros-57b3.onrender.com")


@app.route("/robots.txt")
def robots():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{SITE_URL}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>\n"
        "</urlset>\n"
    )
    return Response(body, mimetype="application/xml")


# ──────────────────────────────────────────────────────────────
# Growth agent chat
# ──────────────────────────────────────────────────────────────
@app.route("/api/agent/chat", methods=["POST"])
def agent_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "No message provided"}), 400

    username = (data.get("username") or "").lstrip("@").lower().strip()
    analysis = _analysis_cache.get(username) or data.get("analysis") or {}
    reply = chat_with_context(username, analysis, message)
    return jsonify({"ok": True, "reply": reply})


# ──────────────────────────────────────────────────────────────
# Raw Apify profile lookup
# ──────────────────────────────────────────────────────────────
@app.route("/api/apify/profile", methods=["GET"])
def apify_profile():
    username = (request.args.get("username") or "").lstrip("@").strip()
    if not username:
        return jsonify({"error": "username is required"}), 400
    try:
        profile = scrape_profile(username, os.getenv("APIFY_API_TOKEN"))
    except Exception:
        return jsonify({"ok": False, "error": "Profile lookup failed"}), 502
    return jsonify({"ok": True, "profile": _profile_to_dict(profile)})


# ──────────────────────────────────────────────────────────────
# Email capture (lead list)
# ──────────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _save_email(email: str) -> None:
    with _db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS emails (email TEXT, created REAL)")
        c.execute("INSERT INTO emails(email, created) VALUES(?,?)", (email, time.time()))


@app.route("/api/email/capture", methods=["POST"])
def email_capture():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    if not email or not _EMAIL_RE.match(email):
        return jsonify({"ok": False, "error": "invalid email"}), 400
    _save_email(email)
    return jsonify({"ok": True})


# ──────────────────────────────────────────────────────────────
# Billing — Stripe checkout (not live yet)
# ──────────────────────────────────────────────────────────────
@app.route("/api/billing/checkout", methods=["POST"])
def billing_checkout():
    # Payments are not live yet. Fail closed with a clear 503 (never a 500 or a
    # raw Stripe object). Real Stripe Checkout session creation gets wired here
    # once STRIPE_SECRET_KEY is set on the host.
    return jsonify({"error": "Payments aren't live yet — coming this week."}), 503


@app.route("/billing/success")
def billing_success():
    return redirect("/", code=302)


@app.route("/billing/cancel")
def billing_cancel():
    return redirect("/", code=302)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

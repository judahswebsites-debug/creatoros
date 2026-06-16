import os
import re
import stripe
import json
import time
import uuid
import sqlite3
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from demo_routes import demo_bp
from scraper import scrape_profile
from analyzer import analyze_profile, analyze_overview, stream_deep_sections, chat_with_context

app = Flask(__name__)
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
CORS(app)
app.register_blueprint(demo_bp)

_supabase_client = None
def _get_supabase():
    global _supabase_client
    if _supabase_client is None:
        url=__import__('os').getenv('SUPABASE_URL',''); key=__import__('os').getenv('SUPABASE_SECRET_KEY','')
        if url and key:
            try:
                from supabase import create_client; _supabase_client=create_client(url,key)
            except: pass
    return _supabase_client
def _get_current_user():
    from flask import request
    auth=request.headers.get('Authorization','')
    if not auth.startswith('Bearer '): return None
    sb=_get_supabase()
    if not sb: return None
    try: return sb.auth.get_user(auth[7:]).user
    except: return None

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
        c.execute(
            "CREATE TABLE IF NOT EXISTS emails "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, username TEXT, created REAL)"
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
        from analyzer import _profile_data as _pd
        overview["_profile_data"] = _pd(profile)
        _job_set(job_id, "overview_ready", data=overview)
        # Deep analysis handled by SSE /api/analyze/stream-deep/<job_id>
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


@app.route("/api/debug-scrape")
def debug_scrape():
    import requests as _req
    username = request.args.get("u", "sam_sulek")
    api_key = os.getenv("BRIGHT_DATA_API_KEY", "")
    base = "https://api.brightdata.com/datasets/v3/scrape"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    ig_url = f"https://www.instagram.com/{username}/"
    results = {}
    for ds_name, ds_id in [("profile", "gd_l1vikfch901nx3by4"), ("reels", "gd_lyclm20il4r5helnj")]:
        try:
            r = _req.post(f"{base}?dataset_id={ds_id}&format=json&include_errors=true",
                         json=[{"url": ig_url}],
                         headers=headers, timeout=60)
            data = r.json()
            if isinstance(data, list) and data:
                results[ds_name] = {"count": len(data), "keys": list(data[0].keys()), "sample": data[0]}
            else:
                results[ds_name] = {"raw": data}
        except Exception as e:
            results[ds_name] = {"error": str(e)}
    return jsonify(results)


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

    user=_get_current_user()
    if user:
        sb=_get_supabase()
        if sb:
            try:
                from datetime import datetime
                mk=datetime.now().strftime('%Y-%m')
                p=(sb.table('profiles').select('plan,scans_this_month,scans_month_key').eq('id',user.id).single().execute().data or {})
                plan=p.get('plan','free'); scans=p.get('scans_this_month',0) if p.get('scans_month_key')==mk else 0
                if scans>={'free':1,'pro':10,'max':999999}.get(plan,1)-1+1:
                    if scans>={'free':1,'pro':10,'max':999999}.get(plan,1):
                        from flask import jsonify; return jsonify({'ok':False,'error':'limit_reached','plan':plan}),403
                sb.table('profiles').update({'scans_this_month':scans+1,'scans_month_key':mk}).eq('id',user.id).execute()
            except: pass
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




@app.route("/api/analyze/stream-deep/<job_id>")
def stream_deep(job_id):
    """SSE endpoint — streams deep analysis sections as Claude generates them."""
    job = _job_get(job_id)
    if not job or not job.get("data"):
        return jsonify({"ok": False, "error": "Job not ready"}), 404
    job_data = job["data"]
    profile_data = job_data.get("_profile_data")
    if not profile_data:
        return jsonify({"ok": False, "error": "Profile data missing"}), 400
    api_key = os.getenv("ANTHROPIC_API_KEY")
    username = (job_data.get("profile") or {}).get("username", "").lower()

    def generate():
        merged = {k: v for k, v in job_data.items() if not k.startswith("_")}
        try:
            for section_name, section_data in stream_deep_sections(profile_data, api_key, job_data):
                merged[section_name] = section_data
                payload = json.dumps({"type": "section", "key": section_name, "data": section_data})
                yield f"data: {payload}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return
        merged["deep_ok"] = True
        if username:
            _analysis_cache[username] = merged
        _job_set(job_id, "complete", data=merged)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

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



@app.route("/api/checkout", methods=["POST"])
def checkout():
    try:
        data = request.get_json(force=True, silent=True) or {}
        plan = (data.get("plan") or "pro").strip().lower()
        prices = {"pro": "price_1TikN9DpHO7O30oqhIbqb2kE", "max": "price_1TilXdDpHO7O30oqdSSpYw23"}
        price_id = prices.get(plan, prices["pro"])
        session = stripe.checkout.Session.create(
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url="https://creatoros-ark3.onrender.com/?session_id={CHECKOUT_SESSION_ID}&upgraded=1",
            cancel_url="https://creatoros-ark3.onrender.com/",
        )
        return jsonify({"ok": True, "url": session.url})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/verify-session")
def verify_session():
    session_id = request.args.get("session_id", "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "session_id required"}), 400
    try:
        sess = stripe.checkout.Session.retrieve(session_id)
        paid = sess.payment_status == "paid" or sess.status == "complete"
        plan = "pro"
        try:
            li = stripe.checkout.Session.list_line_items(sess.id, limit=1)
            if li and li.data:
                price_id = li.data[0].price.id
                if price_id == "price_1TilXdDpHO7O30oqdSSpYw23":
                    plan = "max"
        except Exception:
            pass
        if paid:
            u=_get_current_user()
            if u:
                try:
                    sb=_get_supabase()
                    if sb: sb.table('profiles').update({'plan':plan}).eq('id',u.id).execute()
                except: pass
        return jsonify({"ok": True, "paid": paid, "plan": plan})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/capture-email", methods=["POST"])
def capture_email():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()[:200]
    email = (data.get("email") or "").strip()[:200]
    username = (data.get("username") or "").strip()[:200]
    if not email:
        return jsonify({"ok": False, "error": "email required"}), 400
    with _db() as c:
        c.execute(
            "INSERT INTO emails(name, email, username, created) VALUES(?,?,?,?)",
            (name, email, username, time.time()),
        )
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

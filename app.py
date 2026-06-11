import os
import json
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from demo_routes import demo_bp
from scraper import scrape_profile
from analyzer import analyze_profile, chat_with_context

app = Flask(__name__)
CORS(app)
app.register_blueprint(demo_bp)

# In-memory store for chat context (keyed by username)
_analysis_cache: dict = {}


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
        "profile_pic_url": profile.profile_pic_url,
    }

    _analysis_cache[username.lower()] = result
    return jsonify(result)


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


@app.route("/api/analytics/benchmarks")
def benchmarks():
    username = request.args.get("username", "").lower()
    cached = _analysis_cache.get(username, {})
    er_str = cached.get("analytics", {}).get("avg_engagement_rate", "3.2%")
    try:
        er_val = float(er_str.replace("%", ""))
    except Exception:
        er_val = 3.2

    freq = cached.get("analytics", {}).get("posting_frequency_per_week", "3x / week")
    try:
        freq_val = float(str(freq).replace("x / week", "").replace("x/week", "").strip())
    except Exception:
        freq_val = 3.0

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
            "user_value": 24,
            "top_value": 85,
            "unit": "K",
            "verdict": "Behind",
        },
    ]
    return jsonify({
        "ok": True,
        "metrics": metrics,
        "motivational": "You're <strong>in the top 30%</strong> for engagement in your niche. Increase posting frequency to unlock the next growth tier.",
    })


@app.route("/api/recommendations")
def recommendations():
    recs = [
        {
            "type": "timing",
            "type_color": "#34d399",
            "headline": "Post Tuesday at 7 PM for 40% more reach",
            "body": "Your audience engagement peaks Tuesday evenings. Shifting just 2 posts per week to this window could significantly boost your reach.",
            "stat": "40% reach increase",
            "confidence": 4,
            "next_preview": "Next: Hook optimization tip",
        },
        {
            "type": "content",
            "type_color": "#fbbf24",
            "headline": "Add a strong hook in first 3 seconds",
            "body": "Your top-performing Reels all start with a bold statement. Apply this to every post to increase watch time and algorithm reach.",
            "stat": "3× watch-through rate",
            "confidence": 3,
            "next_preview": "Next: Hashtag strategy",
        },
        {
            "type": "format",
            "type_color": "#818cf8",
            "headline": "Switch to Reels-first strategy",
            "body": "Reels are getting 4× the organic reach of static posts in your niche right now. Prioritize video content this month.",
            "stat": "4× organic reach",
            "confidence": 4,
            "next_preview": "Next: Collaboration opportunity",
        },
    ]
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


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

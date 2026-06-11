import os
import json
from anthropic import Anthropic
from json_repair import repair_json


SYSTEM_PROMPT = """You are CreatorOS — an elite Instagram growth strategist and data analyst.
You analyze Instagram account data and return a precise, actionable JSON growth report.
Always respond with valid JSON only. No markdown, no explanation outside the JSON.

ACCURACY RULES — these are critical:
- overall_score MUST be consistent with sub_scores. It should be roughly the
  average of content_quality, timing_optimization, and growth_momentum
  (within ±5). Never return a low overall_score when sub_scores are high.
- viral_patterns, content_pillars, and viral stats must be grounded in the
  ACTUAL posts provided (their captions, views, likes). Do NOT invent specific
  post names, dates, song titles, or events that are not present in the data.
  If you reference a post, it must come from the supplied captions/snippets.
- When data is sparse or a metric is missing, say so generically rather than
  fabricating a precise number.
- Predicted figures (views/reach/forecast) must be plausible relative to the
  account's real follower count and observed engagement."""


def _build_prompt(profile) -> str:
    posts_summary = []
    for p in profile.posts[:20]:
        posts_summary.append({
            "type": p.type,
            "views": p.views,
            "likes": p.likes,
            "comments": p.comments,
            "hashtags": p.hashtags[:5],
            "caption_snippet": p.caption[:120] if p.caption else "",
            "timestamp": p.timestamp,
        })

    data = {
        "username": profile.username,
        "followers": profile.followers,
        "following": profile.following,
        "bio": profile.bio,
        "category": profile.category,
        "avg_engagement_rate": profile.avg_engagement_rate,
        "posting_frequency_per_week": profile.posting_frequency_per_week,
        "best_posting_days": profile.best_posting_days,
        "engagement_trend": profile.engagement_trend,
        "top_format": profile.top_format,
        "posts_analyzed": posts_summary,
    }

    return f"""Analyze this Instagram account and return a complete JSON growth report.

Account Data:
{json.dumps(data, indent=2)}

Return ONLY valid JSON matching this exact schema:
{{
  "overall_score": <integer 0-100>,
  "sub_scores": {{
    "content_quality": <integer 0-100>,
    "timing_optimization": <integer 0-100>,
    "growth_momentum": <integer 0-100>
  }},
  "bottleneck": "<single most critical growth issue, 1-2 sentences>",
  "next_best_post": {{
    "title": "<content idea title>",
    "hook": "<opening line / hook for the post>",
    "predicted_views": "<e.g. 45K-80K>",
    "estimated_reach": "<e.g. 28K-52K>",
    "confidence_pct": <integer 65-95>,
    "format": "<Reel|Carousel|Static>",
    "best_time": "<e.g. 7:00 PM>",
    "best_day": "<e.g. Tuesday>",
    "script_outline": ["<step 1>", "<step 2>", "<step 3>", "<step 4>", "<step 5>"],
    "caption": "<full caption with emojis>",
    "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
  }},
  "analytics": {{
    "avg_engagement_rate": "<e.g. 4.2%>",
    "posting_frequency_per_week": "<e.g. 3.5x / week>",
    "best_posting_days": ["<Day1>", "<Day2>"],
    "engagement_trend": "<growing|stable|declining>",
    "top_format": "<Reels|Images|Carousels>"
  }},
  "content_pillars": [
    {{"name": "<pillar name>", "avg_views": "<e.g. 32K>", "verdict": "<Strong|Growing|Weak>"}},
    {{"name": "<pillar name>", "avg_views": "<e.g. 18K>", "verdict": "<Strong|Growing|Weak>"}},
    {{"name": "<pillar name>", "avg_views": "<e.g. 9K>", "verdict": "<Strong|Growing|Weak>"}}
  ],
  "viral_patterns": {{
    "what_works": [
      {{"headline": "<pattern name>", "value": "<stat>", "description": "<why it works>", "action": "<do more of this>"}},
      {{"headline": "<pattern name>", "value": "<stat>", "description": "<why it works>", "action": "<do more of this>"}}
    ],
    "what_doesnt": [
      {{"headline": "<pattern name>", "value": "<stat>", "description": "<why it fails>", "action": "<stop or pivot>"}},
      {{"headline": "<pattern name>", "value": "<stat>", "description": "<why it fails>", "action": "<stop or pivot>"}}
    ]
  }},
  "top_tactics": [
    {{"name": "<tactic>", "impact": "<impact description>", "difficulty": "<Easy|Medium|Hard>", "time_to_implement": "<e.g. 1 day>"}},
    {{"name": "<tactic>", "impact": "<impact description>", "difficulty": "<Easy|Medium|Hard>", "time_to_implement": "<e.g. 3 days>"}},
    {{"name": "<tactic>", "impact": "<impact description>", "difficulty": "<Easy|Medium|Hard>", "time_to_implement": "<e.g. 1 week>"}}
  ],
  "video_blueprints": [
    {{
      "rank": 1,
      "title": "<video title>",
      "hook": "<opening hook line>",
      "why": "<why this will perform well>",
      "tags": ["<tag1>", "<tag2>", "<tag3>"],
      "predicted_views": "<e.g. 80K-150K>",
      "saves": "<e.g. 4K-7K>",
      "shares": "<e.g. 2K-4K>",
      "shot_list": ["<shot 1>", "<shot 2>", "<shot 3>", "<shot 4>"],
      "caption": "<full caption>",
      "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
    }},
    {{
      "rank": 2,
      "title": "<video title>",
      "hook": "<opening hook line>",
      "why": "<why this will perform well>",
      "tags": ["<tag1>", "<tag2>"],
      "predicted_views": "<e.g. 50K-90K>",
      "saves": "<e.g. 2K-4K>",
      "shares": "<e.g. 1K-2K>",
      "shot_list": ["<shot 1>", "<shot 2>", "<shot 3>"],
      "caption": "<full caption>",
      "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4"]
    }},
    {{
      "rank": 3,
      "title": "<video title>",
      "hook": "<opening hook line>",
      "why": "<why this will perform well>",
      "tags": ["<tag1>", "<tag2>"],
      "predicted_views": "<e.g. 30K-60K>",
      "saves": "<e.g. 1K-3K>",
      "shares": "<e.g. 800-1.5K>",
      "shot_list": ["<shot 1>", "<shot 2>", "<shot 3>"],
      "caption": "<full caption>",
      "hashtags": ["#tag1", "#tag2", "#tag3"]
    }}
  ],
  "trend_opportunities": [
    {{"name": "<trend name>", "urgency": "<Hot|Rising|Evergreen>", "emoji": "<emoji>", "why": "<why relevant>", "your_angle": "<specific angle for this account>"}},
    {{"name": "<trend name>", "urgency": "<Hot|Rising|Evergreen>", "emoji": "<emoji>", "why": "<why relevant>", "your_angle": "<specific angle for this account>"}}
  ],
  "monetization": {{
    "brand_deal_score": <integer 0-100>,
    "status": "<Ready to monetize|Almost ready|Building foundation>",
    "suggested_rate": "<e.g. $500-$1,200 per post>",
    "niches": ["<niche1>", "<niche2>"],
    "milestone_text": "<what needs to happen next to unlock next monetization tier>"
  }},
  "follower_forecast": {{
    "now": <integer followers>,
    "three_months": <integer>,
    "six_months": <integer>,
    "twelve_months": <integer>,
    "growth_lever": "<single most impactful action to accelerate follower growth>"
  }},
  "scrape_meta": {{
    "posts_scraped": {profile.meta.get('posts_scraped', 0)},
    "reels_scraped": {profile.meta.get('reels_scraped', 0)},
    "avg_engagement_rate": "{profile.avg_engagement_rate}%",
    "scrape_quality": "{profile.meta.get('scrape_quality', 'medium')}"
  }}
}}"""


def analyze_profile(profile, api_key=None) -> dict:
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    client = Anthropic(api_key=key)

    prompt = _build_prompt(profile)

    try:
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0]
        data = json.loads(repair_json(raw))
        data["ok"] = True
        return data
    except Exception as e:
        return {"ok": False, "error": str(e)}


def chat_with_context(username: str, analysis: dict, message: str, api_key=None) -> str:
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    client = Anthropic(api_key=key)

    system = f"""You are CreatorOS Growth Agent — an expert Instagram growth coach.
You have analyzed @{username}'s account. Here is their full growth report:
{json.dumps(analysis, indent=2)}

Answer the user's question with specific, actionable advice based on this data.

FORMATTING RULES — follow these exactly:
- Use short bullet points (•) for lists, not long paragraphs
- Bold key metrics or terms with **asterisks**
- Keep each bullet to 1-2 lines max
- Use section headers (e.g. "**What to do:**") when covering multiple topics
- Never write a wall of text — break everything into scannable chunks
- Lead with the most important point first
- Max 5-6 bullets per response unless the question clearly needs more
- Use specific numbers from the report (engagement rate, follower count, etc.)"""

    try:
        resp = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
        return resp.content[0].text
    except Exception as e:
        return f"Sorry, I couldn't process that: {e}"

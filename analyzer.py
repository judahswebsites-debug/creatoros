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
  account's real follower count and observed engagement.
- For image posts, "views" in the data is an estimated reach derived from likes.
  Use it as-is for avg_views in content_pillars — NEVER output "N/A" or
  "views not reported". Always return a number or a range like "12K"."""


def _profile_data(profile) -> dict:
    posts_summary = []
    for p in profile.posts[:20]:
        views = p.views
        views_note = None
        if not views and p.type != "reel":
            views = (p.likes or 0) * 8
            views_note = "estimated_from_likes"
        posts_summary.append({
            "type": p.type,
            "views": views,
            **({"views_note": views_note} if views_note else {}),
            "likes": p.likes,
            "comments": p.comments,
            "hashtags": p.hashtags[:5],
            "caption_snippet": p.caption[:120] if p.caption else "",
            "timestamp": p.timestamp,
        })

    return {
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


def _build_prompt(profile) -> str:
    data = _profile_data(profile)

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


def _call_claude_json(prompt: str, api_key=None, max_tokens=4096) -> dict:
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    client = Anthropic(api_key=key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
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
    return json.loads(repair_json(raw))


def analyze_profile(profile, api_key=None) -> dict:
    """Full single-shot report (kept for backwards compatibility)."""
    try:
        data = _call_claude_json(_build_prompt(profile), api_key, max_tokens=4096)
        data["ok"] = True
        return data
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _overview_prompt(profile) -> str:
    data = _profile_data(profile)
    return f"""Analyze this Instagram account and return the CORE growth snapshot as JSON.

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
  "scrape_meta": {{
    "posts_scraped": {profile.meta.get('posts_scraped', 0)},
    "reels_scraped": {profile.meta.get('reels_scraped', 0)},
    "avg_engagement_rate": "{profile.avg_engagement_rate}%",
    "scrape_quality": "{profile.meta.get('scrape_quality', 'medium')}"
  }}
}}"""


def _deep_prompt(profile, overview=None) -> str:
    data = _profile_data(profile)
    ctx = ""
    if overview:
        ctx = f"\nYour earlier snapshot (stay consistent with it):\n{json.dumps({k: overview.get(k) for k in ('overall_score', 'bottleneck', 'analytics') if overview.get(k)}, indent=2)}\n"
    return f"""Produce the DEEP growth modules for this Instagram account as JSON.
{ctx}
Account Data:
{json.dumps(data, indent=2)}

Return ONLY valid JSON matching this exact schema:
{{
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
    {{"rank": 1, "title": "<video title>", "hook": "<opening hook line>", "why": "<why this performs>", "tags": ["<tag1>", "<tag2>", "<tag3>"], "predicted_views": "<e.g. 80K-150K>", "saves": "<e.g. 4K-7K>", "shares": "<e.g. 2K-4K>", "shot_list": ["<shot 1>", "<shot 2>", "<shot 3>", "<shot 4>"], "caption": "<full caption>", "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]}},
    {{"rank": 2, "title": "<video title>", "hook": "<opening hook line>", "why": "<why this performs>", "tags": ["<tag1>", "<tag2>"], "predicted_views": "<e.g. 50K-90K>", "saves": "<e.g. 2K-4K>", "shares": "<e.g. 1K-2K>", "shot_list": ["<shot 1>", "<shot 2>", "<shot 3>"], "caption": "<full caption>", "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4"]}},
    {{"rank": 3, "title": "<video title>", "hook": "<opening hook line>", "why": "<why this performs>", "tags": ["<tag1>", "<tag2>"], "predicted_views": "<e.g. 30K-60K>", "saves": "<e.g. 1K-3K>", "shares": "<e.g. 800-1.5K>", "shot_list": ["<shot 1>", "<shot 2>", "<shot 3>"], "caption": "<full caption>", "hashtags": ["#tag1", "#tag2", "#tag3"]}}
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
    "milestone_text": "<what unlocks the next monetization tier>"
  }},
  "follower_forecast": {{
    "now": <integer followers>,
    "three_months": <integer>,
    "six_months": <integer>,
    "twelve_months": <integer>,
    "growth_lever": "<single most impactful action to accelerate growth>"
  }}
}}"""


def analyze_overview(profile, api_key=None) -> dict:
    """Fast first-paint using Haiku for speed: score, bottleneck, next best post, analytics."""
    try:
        key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        client = Anthropic(api_key=key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _overview_prompt(profile)}],
        )
        raw = message.content[0].text.strip()
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


def analyze_deep(profile, api_key=None, overview=None) -> dict:
    """Heavy modules: pillars, viral patterns, tactics, blueprints, trends, monetization, forecast."""
    try:
        data = _call_claude_json(_deep_prompt(profile, overview), api_key, max_tokens=4096)
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
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
        return resp.content[0].text
    except Exception as e:
        return f"Sorry, I couldn't process that: {e}"




_STREAM_SECTIONS = [
    ("content_pillars",    '[{"name":"<pillar>","avg_views":"<32K>","verdict":"<Strong|Growing|Weak>"},{"name":"<pillar>","avg_views":"<18K>","verdict":"<Strong|Growing|Weak>"},{"name":"<pillar>","avg_views":"<9K>","verdict":"<Strong|Growing|Weak>"}]'),
    ("viral_patterns",     '{"what_works":[{"headline":"<p>","value":"<stat>","description":"<why>","action":"<do>"},{"headline":"<p>","value":"<stat>","description":"<why>","action":"<do>"}],"what_doesnt":[{"headline":"<p>","value":"<stat>","description":"<why>","action":"<pivot>"},{"headline":"<p>","value":"<stat>","description":"<why>","action":"<pivot>"}]}'),
    ("top_tactics",        '[{"name":"<tactic>","impact":"<1 sentence>","difficulty":"<Easy|Medium|Hard>","time_to_implement":"<1 day>"},{"name":"<tactic>","impact":"<1 sentence>","difficulty":"<Easy|Medium|Hard>","time_to_implement":"<3 days>"},{"name":"<tactic>","impact":"<1 sentence>","difficulty":"<Easy|Medium|Hard>","time_to_implement":"<1 week>"}]'),
    ("video_blueprints",   '[{"rank":1,"title":"<t>","hook":"<h>","why":"<1 sentence>","tags":["<t1>","<t2>","<t3>"],"predicted_views":"<80K-150K>","saves":"<4K-7K>","shares":"<2K-4K>","caption":"<under 25 words>","hashtags":["#tag1","#tag2","#tag3","#tag4","#tag5"]},{"rank":2,"title":"<t>","hook":"<h>","why":"<1 sentence>","tags":["<t1>","<t2>"],"predicted_views":"<50K-90K>","saves":"<2K-4K>","shares":"<1K-2K>","caption":"<under 25 words>","hashtags":["#tag1","#tag2","#tag3","#tag4"]},{"rank":3,"title":"<t>","hook":"<h>","why":"<1 sentence>","tags":["<t1>","<t2>"],"predicted_views":"<30K-60K>","saves":"<1K-3K>","shares":"<800-1.5K>","caption":"<under 25 words>","hashtags":["#tag1","#tag2","#tag3"]}]'),
    ("trend_opportunities",'[{"name":"<trend>","urgency":"<Hot|Rising|Evergreen>","emoji":"<e>","why":"<why>","your_angle":"<angle>"},{"name":"<trend>","urgency":"<Hot|Rising|Evergreen>","emoji":"<e>","why":"<why>","your_angle":"<angle>"}]'),
    ("follower_forecast",  '{"now":<followers int>,"three_months":<int>,"six_months":<int>,"twelve_months":<int>,"growth_lever":"<single most impactful action>"}'),
    ("monetization",       '{"brand_deal_score":85,"status":"<Ready to monetize|Almost ready|Building foundation>","suggested_rate":"<$500-$1,200 per post>","niches":["<niche1>","<niche2>"],"milestone_text":"<what unlocks next tier>"}'),
]


def stream_deep_sections(profile_data: dict, api_key=None, overview=None):
    """Generator yielding (section_name, parsed_data) as Claude streams — true token streaming."""
    ctx = _ctx(overview) if overview else ""
    sections_fmt = "\n".join(f"---{name}---\n{schema}" for name, schema in _STREAM_SECTIONS)
    prompt = f"""Analyze this Instagram account. Output EVERY section in exact order using the delimiter format. Replace schema placeholders with real data. Each value must be valid JSON.
{ctx}
Account Data:
{json.dumps(profile_data, indent=2)}

Output format:
{sections_fmt}
---done---"""

    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    client = Anthropic(api_key=key)
    section_names = [name for name, _ in _STREAM_SECTIONS]
    buffer = ""
    current_section = None
    section_buffer = ""

    def _find_marker(text):
        best_idx, best_name = -1, None
        for name in section_names + ["done"]:
            marker = f"---{name}---"
            idx = text.find(marker)
            if idx >= 0 and (best_idx < 0 or idx < best_idx):
                best_idx, best_name = idx, name
        return best_name, best_idx

    try:
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for chunk in stream.text_stream:
                buffer += chunk
                while True:
                    marker_name, marker_idx = _find_marker(buffer)
                    if marker_name is None:
                        if current_section and len(buffer) > 20:
                            section_buffer += buffer[:-20]
                            buffer = buffer[-20:]
                        break
                    if current_section is not None:
                        section_json = (section_buffer + buffer[:marker_idx]).strip()
                        try:
                            section_data = json.loads(repair_json(section_json))
                            yield current_section, section_data
                        except Exception:
                            pass
                        section_buffer = ""
                    if marker_name == "done":
                        return
                    current_section = marker_name
                    buffer = buffer[marker_idx + len(f"---{marker_name}---"):]
    except Exception:
        return

def _ctx(overview):
    if not overview:
        return ""
    return f"\nEarlier snapshot (stay consistent):\n{json.dumps({k: overview.get(k) for k in ('overall_score', 'bottleneck', 'analytics') if overview.get(k)}, indent=2)}\n"


def analyze_deep_phase1(profile, api_key=None, overview=None) -> dict:
    """Phase 1: content pillars + viral patterns."""
    pdata = _profile_data(profile)
    prompt = f"""Analyze this Instagram account and return ONLY content pillars and viral patterns as JSON.
{_ctx(overview)}
Account Data:
{json.dumps(pdata, indent=2)}

Return ONLY valid JSON:
{{
  "content_pillars": [
    {{"name": "<pillar name>", "avg_views": "<e.g. 32K>", "verdict": "<Strong|Growing|Weak>"}},
    {{"name": "<pillar name>", "avg_views": "<e.g. 18K>", "verdict": "<Strong|Growing|Weak>"}},
    {{"name": "<pillar name>", "avg_views": "<e.g. 9K>", "verdict": "<Strong|Growing|Weak>"}}
  ],
  "viral_patterns": {{
    "what_works": [
      {{"headline": "<pattern>", "value": "<stat>", "description": "<why it works>", "action": "<do more>"}},
      {{"headline": "<pattern>", "value": "<stat>", "description": "<why it works>", "action": "<do more>"}}
    ],
    "what_doesnt": [
      {{"headline": "<pattern>", "value": "<stat>", "description": "<why it fails>", "action": "<stop or pivot>"}},
      {{"headline": "<pattern>", "value": "<stat>", "description": "<why it fails>", "action": "<stop or pivot>"}}
    ]
  }}
}}"""
    try:
        data = _call_claude_json(prompt, api_key, max_tokens=1000)
        data["ok"] = True
        return data
    except Exception as e:
        return {"ok": False, "error": str(e)}


def analyze_deep_phase2(profile, api_key=None, overview=None) -> dict:
    """Phase 2: top tactics + video blueprints."""
    pdata = _profile_data(profile)
    prompt = f"""Analyze this Instagram account and return ONLY growth tactics and video blueprints as JSON.
{_ctx(overview)}
Account Data:
{json.dumps(pdata, indent=2)}

Return ONLY valid JSON:
{{
  "top_tactics": [
    {{"name": "<tactic>", "impact": "<description>", "difficulty": "<Easy|Medium|Hard>", "time_to_implement": "<e.g. 1 day>"}},
    {{"name": "<tactic>", "impact": "<description>", "difficulty": "<Easy|Medium|Hard>", "time_to_implement": "<e.g. 3 days>"}},
    {{"name": "<tactic>", "impact": "<description>", "difficulty": "<Easy|Medium|Hard>", "time_to_implement": "<e.g. 1 week>"}}
  ],
  "video_blueprints": [
    {{"rank": 1, "title": "<title>", "hook": "<hook>", "why": "<why>", "tags": ["<t1>", "<t2>", "<t3>"], "predicted_views": "<80K-150K>", "saves": "<4K-7K>", "shares": "<2K-4K>", "shot_list": ["<s1>", "<s2>", "<s3>", "<s4>"], "caption": "<caption>", "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]}},
    {{"rank": 2, "title": "<title>", "hook": "<hook>", "why": "<why>", "tags": ["<t1>", "<t2>"], "predicted_views": "<50K-90K>", "saves": "<2K-4K>", "shares": "<1K-2K>", "shot_list": ["<s1>", "<s2>", "<s3>"], "caption": "<caption>", "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4"]}},
    {{"rank": 3, "title": "<title>", "hook": "<hook>", "why": "<why>", "tags": ["<t1>", "<t2>"], "predicted_views": "<30K-60K>", "saves": "<1K-3K>", "shares": "<800-1.5K>", "shot_list": ["<s1>", "<s2>", "<s3>"], "caption": "<caption>", "hashtags": ["#tag1", "#tag2", "#tag3"]}}
  ]
}}"""
    try:
        data = _call_claude_json(prompt, api_key, max_tokens=2000)
        data["ok"] = True
        return data
    except Exception as e:
        return {"ok": False, "error": str(e)}


def analyze_deep_phase3(profile, api_key=None, overview=None) -> dict:
    """Phase 3: trend opportunities + monetization + follower forecast."""
    pdata = _profile_data(profile)
    prompt = f"""Analyze this Instagram account and return ONLY trends, monetization, and follower forecast as JSON.
{_ctx(overview)}
Account Data:
{json.dumps(pdata, indent=2)}

Return ONLY valid JSON:
{{
  "trend_opportunities": [
    {{"name": "<trend>", "urgency": "<Hot|Rising|Evergreen>", "emoji": "<emoji>", "why": "<why relevant>", "your_angle": "<specific angle>"}},
    {{"name": "<trend>", "urgency": "<Hot|Rising|Evergreen>", "emoji": "<emoji>", "why": "<why relevant>", "your_angle": "<specific angle>"}}
  ],
  "monetization": {{
    "brand_deal_score": 85,
    "status": "<Ready to monetize|Almost ready|Building foundation>",
    "suggested_rate": "<e.g. $500-$1,200 per post>",
    "niches": ["<niche1>", "<niche2>"],
    "milestone_text": "<what unlocks the next tier>"
  }},
  "follower_forecast": {{
    "now": 1000,
    "three_months": 1200,
    "six_months": 1500,
    "twelve_months": 2000,
    "growth_lever": "<single most impactful action>"
  }}
}}"""
    try:
        data = _call_claude_json(prompt, api_key, max_tokens=900)
        data["ok"] = True
        return data
    except Exception as e:
        return {"ok": False, "error": str(e)}

import hashlib
import random
from flask import Blueprint, request, jsonify

demo_bp = Blueprint("demo_bp", __name__)

FORMAT_TEMPLATES = [
    {
        "type": "format",
        "headline": "Reels outperform your images by {MUL}×",
        "body": "Your Reels are getting {X}% more engagement than static posts. The algorithm is actively pushing short-form video in your niche — and your audience responds to it.",
        "stat": "{X}% higher reach on video content",
    },
    {
        "type": "format",
        "headline": "Carousels drive {X}% more saves than single posts",
        "body": "Multi-slide carousels are your hidden growth lever. They get held longer, saved more, and reshared to Stories — tripling your content lifespan.",
        "stat": "{X}% higher save rate on carousels",
    },
    {
        "type": "format",
        "headline": "Behind-the-scenes content gets {MUL}× more DMs",
        "body": "Your audience is craving authenticity. Raw, unpolished behind-the-scenes content in your top {TOP}% of posts for comment engagement.",
        "stat": "Top {TOP}% of posts by comment engagement",
    },
]

TIMING_TEMPLATES = [
    {
        "type": "timing",
        "headline": "Posts on {DAY} get {X}% more reach",
        "body": "Your audience is most active {DAY} evenings. Posting at {TIME} on {DAY} puts your content in front of followers when they're in scroll mode — not rush mode.",
        "stat": "Peak window: {DAY} at {TIME}",
    },
    {
        "type": "timing",
        "headline": "Your {TIME} posts reach {X}% more people",
        "body": "Early {TIME} posts catch your audience before their feeds fill up. You're consistently in the top {TOP}% of reach during this window compared to other posting times.",
        "stat": "Top {TOP}% reach during {TIME} window",
    },
    {
        "type": "timing",
        "headline": "{DAY} + {DAY2} are your power days",
        "body": "Accounts in your niche see a {X}% engagement spike mid-week. Your followers are online and ready to interact — this is when the algorithm rewards consistent posters.",
        "stat": "{X}% above-average engagement on {DAY}/{DAY2}",
    },
]

CONTENT_TEMPLATES = [
    {
        "type": "content",
        "headline": "Posts with '{V}' in the hook get {V2} more views",
        "body": "Your top-performing posts all open with a bold claim or surprising statistic. The first 3 seconds decide everything — and your data confirms hooks that challenge assumptions win.",
        "stat": "{V2} average additional views with strong hook",
    },
    {
        "type": "content",
        "headline": "Educational content drives {X}% more shares",
        "body": "When you teach something specific and actionable, your audience shares it. Your 'how-to' style posts are in the top {TOP}% of share rate across your entire feed.",
        "stat": "Top {TOP}% share rate on educational posts",
    },
    {
        "type": "content",
        "headline": "Niche-specific content gets {MUL}× the saves",
        "body": "Hyper-specific posts that speak directly to your niche outperform broad content every time. Your audience saves them to come back — signaling high value to the algorithm.",
        "stat": "{MUL}× save rate vs. general content",
    },
]

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIMES = ["7:00 AM", "12:00 PM", "6:00 PM", "8:00 PM", "9:30 PM"]
COLORS = {"format": "#818cf8", "timing": "#34d399", "content": "#fbbf24"}


def _fill(template: dict, rng: random.Random) -> dict:
    X = rng.randint(22, 67)
    MUL = rng.choice([2, 3, 4])
    V = rng.choice(["Wait for it", "Nobody tells you", "Controversial take", "Stop doing this"])
    V2 = f"{rng.randint(4, 18)}K"
    DAY = rng.choice(DAYS)
    DAY2 = rng.choice([d for d in DAYS if d != DAY])
    TIME = rng.choice(TIMES)
    TOP = rng.randint(5, 25)

    def sub(s):
        return (s.replace("{X}", str(X)).replace("{MUL}", str(MUL))
                 .replace("{V}", V).replace("{V2}", V2)
                 .replace("{DAY}", DAY).replace("{DAY2}", DAY2)
                 .replace("{TIME}", TIME).replace("{TOP}", str(TOP)))

    return {
        "type": template["type"],
        "color": COLORS[template["type"]],
        "headline": sub(template["headline"]),
        "body": sub(template["body"]),
        "stat": sub(template["stat"]),
    }


@demo_bp.route("/api/demo/analyze", methods=["POST"])
def demo_analyze():
    data = request.get_json(silent=True) or {}
    handle = (data.get("handle") or "demo").lstrip("@").lower().strip()

    seed = int(hashlib.md5(handle.encode()).hexdigest(), 16) % (2**31)
    rng = random.Random(seed)

    follower_count = rng.randint(1200, 280000)
    avg_er = round(rng.uniform(1.8, 9.4), 1)
    posts_analyzed = rng.randint(12, 30)

    insights = [
        _fill(rng.choice(FORMAT_TEMPLATES), rng),
        _fill(rng.choice(TIMING_TEMPLATES), rng),
        _fill(rng.choice(CONTENT_TEMPLATES), rng),
    ]

    return jsonify({
        "handle": handle,
        "follower_count": follower_count,
        "avg_engagement_rate": avg_er,
        "posts_analyzed": posts_analyzed,
        "insights": insights,
    })

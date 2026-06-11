import anthropic
import json
from instagram_fetcher import ProfileData, compute_stats


def analyze_and_recommend(profile: ProfileData, api_key: str) -> dict:
    stats = compute_stats(profile)

    client = anthropic.Anthropic(api_key=api_key)

    # Build a compact summary for the prompt
    top_captions = [
        f"- [{p.likes} likes, {p.comments} comments] {p.caption[:200]}"
        for p in sorted(profile.posts, key=lambda x: x.likes, reverse=True)[:8]
    ]

    prompt = f"""You are an expert Instagram content strategist and data analyst. Your job is to analyze an influencer's Instagram profile and provide actionable, specific recommendations for their next post or video to maximize views and engagement — similar to how keyword optimization works for Amazon listings.

## Profile: @{profile.username}
- **Name**: {profile.full_name}
- **Bio**: {profile.biography}
- **Followers**: {profile.followers:,}
- **Engagement Rate**: {stats.get('engagement_rate', 0)}%
- **Avg Likes**: {stats.get('avg_likes', 0)} | **Avg Comments**: {stats.get('avg_comments', 0)}
- **Content Mix**: {stats.get('video_count', 0)} videos (avg {stats.get('avg_video_likes', 0)} likes) vs {stats.get('image_count', 0)} images (avg {stats.get('avg_image_likes', 0)} likes)

## Top Hashtags Used:
{', '.join(['#' + h for h in stats.get('top_hashtags', [])[:15]])}

## Top Caption Keywords:
{', '.join(stats.get('top_caption_words', [])[:15])}

## Best Performing Posts (by engagement):
{chr(10).join(top_captions)}

---

Analyze this data and provide a JSON response with the following structure:
{{
  "content_analysis": {{
    "niche": "what niche/category this account is in",
    "content_pillars": ["3-4 recurring content themes you identified"],
    "what_works": ["3-4 specific observations about what drives high engagement"],
    "what_underperforms": ["2-3 patterns seen in lower-performing content"],
    "format_winner": "video or image, and why based on the data"
  }},
  "next_post_recommendations": [
    {{
      "rank": 1,
      "title": "specific post/video concept title",
      "concept": "2-3 sentence description of exactly what to make",
      "why_it_will_perform": "data-backed reason this should get high views",
      "format": "Reel / Carousel / Single Image / Story",
      "hook_ideas": ["2-3 specific opening lines or visual hooks"],
      "caption_strategy": "what tone, length, and structure to use",
      "hashtag_strategy": {{
        "must_include": ["5 hashtags that have performed well for this account"],
        "new_to_try": ["5 trending or adjacent hashtags to expand reach"],
        "avoid": ["hashtags that seem oversaturated or off-brand"]
      }},
      "best_time_to_post": "day/time recommendation based on content type",
      "collab_opportunity": "any relevant creator or brand to tag/collab with"
    }},
    {{
      "rank": 2,
      "title": "...",
      "concept": "...",
      "why_it_will_perform": "...",
      "format": "...",
      "hook_ideas": [],
      "caption_strategy": "...",
      "hashtag_strategy": {{"must_include": [], "new_to_try": [], "avoid": []}},
      "best_time_to_post": "...",
      "collab_opportunity": "..."
    }},
    {{
      "rank": 3,
      "title": "...",
      "concept": "...",
      "why_it_will_perform": "...",
      "format": "...",
      "hook_ideas": [],
      "caption_strategy": "...",
      "hashtag_strategy": {{"must_include": [], "new_to_try": [], "avoid": []}},
      "best_time_to_post": "...",
      "collab_opportunity": "..."
    }}
  ],
  "growth_insights": {{
    "engagement_health": "assessment of their current engagement rate vs industry benchmarks",
    "audience_signals": "what the comments/likes pattern suggests about their audience",
    "content_gap": "a type of content their audience likely wants but they haven't tried",
    "quick_win": "one immediate change they can make to any future post for better reach"
  }}
}}

Be extremely specific — generic advice is useless. Base everything on the actual data provided."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text

    # Extract JSON from response
    json_start = raw.find("{")
    json_end = raw.rfind("}") + 1
    if json_start != -1 and json_end > json_start:
        analysis = json.loads(raw[json_start:json_end])
    else:
        analysis = {"error": "Could not parse AI response", "raw": raw}

    return {
        "profile": {
            "username": profile.username,
            "full_name": profile.full_name,
            "biography": profile.biography,
            "followers": profile.followers,
            "following": profile.following,
            "post_count": profile.post_count,
            "is_verified": profile.is_verified,
        },
        "stats": stats,
        "analysis": analysis,
    }

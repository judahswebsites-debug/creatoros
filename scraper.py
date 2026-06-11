import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from apify_client import ApifyClient


@dataclass
class Post:
    url: str = ""
    type: str = "image"
    views: int = 0
    likes: int = 0
    comments: int = 0
    timestamp: str = ""
    hashtags: list = field(default_factory=list)
    caption: str = ""


@dataclass
class Profile:
    username: str = ""
    full_name: str = ""
    followers: int = 0
    following: int = 0
    bio: str = ""
    category: str = ""
    posts_count: int = 0
    profile_pic_url: str = ""
    posts: list = field(default_factory=list)
    avg_engagement_rate: float = 0.0
    posting_frequency_per_week: float = 0.0
    best_posting_days: list = field(default_factory=list)
    engagement_trend: str = "stable"
    top_format: str = "Reels"
    meta: dict = field(default_factory=dict)


def _compute_analytics(profile: Profile) -> None:
    posts = profile.posts
    if not posts:
        return

    followers = max(profile.followers, 1)

    engagement_rates = []
    for p in posts:
        er = (p.likes + p.comments) / followers * 100
        engagement_rates.append(er)

    profile.avg_engagement_rate = round(sum(engagement_rates) / len(engagement_rates), 2)

    day_counts: dict = {}
    for p in posts:
        if p.timestamp:
            try:
                dt = datetime.fromisoformat(p.timestamp.replace("Z", "+00:00"))
                day = dt.strftime("%A")
                day_counts[day] = day_counts.get(day, 0) + 1
            except Exception:
                pass

    if day_counts:
        sorted_days = sorted(day_counts, key=day_counts.get, reverse=True)
        profile.best_posting_days = sorted_days[:3]

        # Compute actual date range for accurate frequency
        timestamps = []
        for p in posts:
            if p.timestamp:
                try:
                    timestamps.append(datetime.fromisoformat(p.timestamp.replace("Z", "+00:00")))
                except Exception:
                    pass
        if len(timestamps) >= 2:
            date_range_days = max(1, (max(timestamps) - min(timestamps)).days)
            profile.posting_frequency_per_week = round(len(posts) / date_range_days * 7, 1)
        else:
            profile.posting_frequency_per_week = 0.0

    reel_count = sum(1 for p in posts if p.type in ("reel", "video"))
    image_count = len(posts) - reel_count
    profile.top_format = "Reels" if reel_count >= image_count else "Images"

    # Posts are newest-first from Apify; [:half] = recent, [half:] = older
    half = len(posts) // 2
    if half > 0:
        recent_avg = sum(engagement_rates[:half]) / half
        older_avg = sum(engagement_rates[half:]) / max(1, len(posts) - half)
        if recent_avg > older_avg * 1.1:
            profile.engagement_trend = "growing"
        elif recent_avg < older_avg * 0.9:
            profile.engagement_trend = "declining"
        else:
            profile.engagement_trend = "stable"


def scrape_profile(username: str, apify_token=None) -> Profile:
    token = apify_token or os.getenv("APIFY_API_TOKEN", "")
    client = ApifyClient(token)

    profile = Profile(username=username)
    posts: list[Post] = []

    profile_result = None
    reel_items = []

    # Profile scraper
    try:
        profile_run = client.actor("apify/instagram-profile-scraper").call(
            run_input={
                "usernames": [username],
                "resultsType": "details",
            }
        )
        for item in client.dataset(profile_run["defaultDatasetId"]).iterate_items():
            profile_result = item
            break
    except Exception as e:
        print(f"Profile scrape error: {e}")

    # Reel/post scraper
    try:
        reel_run = client.actor("apify/instagram-reel-scraper").call(
            run_input={
                "username": [username],
                "resultsLimit": 30,
            }
        )
        for item in client.dataset(reel_run["defaultDatasetId"]).iterate_items():
            reel_items.append(item)
    except Exception as e:
        print(f"Reel scrape error: {e}")

    if profile_result:
        profile.username = profile_result.get("username", username)
        profile.full_name = profile_result.get("fullName", "")
        profile.followers = profile_result.get("followersCount", 0)
        profile.following = profile_result.get("followsCount", 0)
        profile.bio = profile_result.get("biography", "")
        profile.category = profile_result.get("businessCategoryName", "Creator")
        profile.posts_count = profile_result.get("postsCount", 0)
        profile.profile_pic_url = profile_result.get("profilePicUrl", "")

    for item in reel_items:
        p = Post()
        p.url = item.get("url", "")
        raw_type = (item.get("type", "") or item.get("productType", "") or "").lower()
        if raw_type in ("video", "reel", "clips") or "reel" in p.url.lower() or item.get("isVideo"):
            p.type = "reel"
        else:
            p.type = "image"
        p.views = item.get("videoViewCount") or item.get("viewsCount") or item.get("videoPlayCount") or 0
        p.likes = item.get("likesCount", 0)
        p.comments = item.get("commentsCount", 0)
        p.timestamp = item.get("timestamp", "")
        caption_raw = item.get("caption", "") or ""
        # Use Apify's pre-parsed hashtags list; fall back to regex on caption
        raw_tags = item.get("hashtags") or []
        if raw_tags:
            p.hashtags = [f"#{t}" if not t.startswith("#") else t for t in raw_tags]
        else:
            import re
            p.hashtags = re.findall(r"#\w+", caption_raw)
        p.caption = caption_raw
        posts.append(p)

    profile.posts = posts

    reels_count = sum(1 for p in posts if p.type in ("reel", "video"))
    images_count = len(posts) - reels_count
    all_tags: set = set()
    for p in posts:
        all_tags.update(p.hashtags)

    profile.meta = {
        "posts_scraped": len(posts),
        "reels_scraped": reels_count,
        "images_scraped": images_count,
        "hashtags_analyzed": len(all_tags),
        "scrape_quality": "high" if len(posts) >= 20 else "medium" if len(posts) >= 10 else "low",
        "actors_used": ["apify/instagram-profile-scraper", "apify/instagram-reel-scraper"],
        "data_sources": ["profile", "reels"],
    }

    _compute_analytics(profile)
    return profile

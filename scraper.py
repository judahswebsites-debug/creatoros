import os
import re
import time
import requests
from dataclasses import dataclass, field
from datetime import datetime

BRIGHT_DATA_BASE = "https://api.brightdata.com/datasets/v3"
BRIGHT_DATA_PROFILE_DATASET = "gd_l1vikfch901nx3by4"
BRIGHT_DATA_POSTS_DATASET = "gd_lk5ns7kz21pck8jpis"

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

def _compute_analytics(profile):
    posts = profile.posts
    if not posts:
        return
    followers = max(profile.followers, 1)
    engagement_rates = []
    for p in posts:
        engagement_rates.append((p.likes + p.comments) / followers * 100)
    profile.avg_engagement_rate = round(sum(engagement_rates) / len(engagement_rates), 2)
    day_counts = {}
    for p in posts:
        if p.timestamp:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(p.timestamp.replace("Z", "+00:00"))
                day = dt.strftime("%A")
                day_counts[day] = day_counts.get(day, 0) + 1
            except Exception:
                pass
    if day_counts:
        profile.best_posting_days = sorted(day_counts, key=day_counts.get, reverse=True)[:3]
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
    reel_count = sum(1 for p in posts if p.type in ("reel", "video"))
    profile.top_format = "Reels" if reel_count >= len(posts) - reel_count else "Images"
    reel_views = [p.views for p in posts if p.type in ("reel", "video") and p.views]
    profile.meta["avg_reel_views"] = round(sum(reel_views) / len(reel_views)) if reel_views else 0
    half = len(posts) // 2
    if half > 0:
        recent_avg = sum(engagement_rates[:half]) / half
        older_avg = sum(engagement_rates[half:]) / max(1, len(posts) - half)
        if recent_avg > older_avg * 1.1:
            profile.engagement_trend = "growing"
        elif recent_avg < older_avg * 0.9:
            profile.engagement_trend = "declining"

def _bright_data_headers(api_key):
    return {"Authorization": f"Bearer {api_key}"}

def _scrape_dataset(dataset_id, payload, api_key):
    url = f"{BRIGHT_DATA_BASE}/scrape"
    params = {"dataset_id": dataset_id, "include_errors": "true"}
    try:
        resp = requests.post(url, params=params, json={"input": payload},
                             headers=_bright_data_headers(api_key), timeout=120)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if "snapshot_id" in data:
                return _poll_snapshot(data["snapshot_id"], api_key)
            return data.get("results", data.get("data", [data]))
    except Exception:
        pass
    return []

def _poll_snapshot(snapshot_id, api_key, max_wait=90):
    url = f"{BRIGHT_DATA_BASE}/snapshot/{snapshot_id}"
    headers = _bright_data_headers(api_key)
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else data.get("results", data.get("data", []))
            if resp.status_code == 202:
                time.sleep(5)
                continue
        except Exception:
            pass
        time.sleep(5)
    return []

def scrape_profile(username, api_key=None):
    api_key = api_key or os.getenv("BRIGHT_DATA_API_KEY", "")
    if not api_key:
        raise ValueError("BRIGHT_DATA_API_KEY is not set")
    ig_url = f"https://www.instagram.com/{username}/"
    profile_items = _scrape_dataset(BRIGHT_DATA_PROFILE_DATASET, [{"url": ig_url}], api_key)
    post_items_raw = _scrape_dataset(BRIGHT_DATA_POSTS_DATASET, [{"url": ig_url, "num_of_posts": 30}], api_key)
    profile = Profile(username=username)
    posts = []
    profile_data = None
    mixed_post_items = []
    for item in profile_items:
        if item.get("followers") is not None and not item.get("post_url"):
            profile_data = item
        else:
            mixed_post_items.append(item)
    if profile_data:
        profile.username = profile_data.get("username", username)
        profile.full_name = profile_data.get("full_name", "") or profile_data.get("name", "")
        profile.followers = profile_data.get("followers", 0) or 0
        profile.following = profile_data.get("following", 0) or 0
        profile.bio = profile_data.get("biography", "") or profile_data.get("bio", "") or ""
        profile.category = profile_data.get("category", "") or "Creator"
        profile.posts_count = profile_data.get("posts", 0) or profile_data.get("media_count", 0) or 0
        profile.profile_pic_url = profile_data.get("profile_pic_url", "") or ""
    seen_urls = set()
    for item in mixed_post_items + post_items_raw:
        p = Post()
        p.url = item.get("post_url", "") or item.get("url", "") or item.get("shortcode", "")
        if p.url in seen_urls:
            continue
        seen_urls.add(p.url)
        raw_type = (item.get("type", "") or item.get("media_type", "") or "").lower()
        if raw_type in ("video", "reel", "clips") or "reel" in str(p.url).lower() or item.get("is_video"):
            p.type = "reel"
        p.views = item.get("video_view_count", 0) or item.get("views", 0) or item.get("play_count", 0) or 0
        p.likes = item.get("likes", 0) or item.get("like_count", 0) or 0
        p.comments = item.get("comments", 0) or item.get("comments_count", 0) or 0
        p.timestamp = item.get("timestamp", "") or item.get("date_posted", "") or item.get("taken_at", "") or ""
        caption_raw = item.get("description", "") or item.get("caption", "") or ""
        raw_tags = item.get("hashtags") or []
        p.hashtags = [f"#{t}" if not t.startswith("#") else t for t in raw_tags] if raw_tags else re.findall(r"#\w+", caption_raw)
        p.caption = caption_raw
        posts.append(p)
    profile.posts = posts
    reels_count = sum(1 for p in posts if p.type in ("reel", "video"))
    all_tags = set(t for p in posts for t in p.hashtags)
    profile.meta = {
        "posts_scraped": len(posts), "reels_scraped": reels_count,
        "images_scraped": len(posts) - reels_count, "hashtags_analyzed": len(all_tags),
        "scrape_quality": "high" if len(posts) >= 20 else "medium" if len(posts) >= 10 else "low",
        "data_sources": ["bright_data"],
    }
    _compute_analytics(profile)
    return profile

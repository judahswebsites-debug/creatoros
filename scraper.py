import os
import re
import time
import requests
from dataclasses import dataclass, field
from datetime import datetime


BRIGHT_DATA_BASE = "https://api.brightdata.com/datasets/v3"
BRIGHT_DATA_DATASET_ID = "gd_l1vikfch901nx3by4"


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
        else:
            profile.engagement_trend = "stable"


def _bright_data_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}



def _scrape_and_wait(username: str, api_key: str) -> list:
    url = f"{BRIGHT_DATA_BASE}/scrape"
    params = {"dataset_id": BRIGHT_DATA_DATASET_ID, "include_errors": "true"}
    payload = {"input": [{"url": f"https://www.instagram.com/{username}/"}]}
    resp = requests.post(url, params=params, json=payload, headers=_bright_data_headers(api_key), timeout=60)
    resp.raise_for_status()
    data = resp.json()
    # Synchronous response — data returned directly
    if isinstance(data, list) and data:
        return data
    # Async response — poll until ready
    # Handle all sync response formats
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "snapshot_id" not in data:
        return [data]
    snapshot_id = data.get("snapshot_id") if isinstance(data, dict) else None
    if not snapshot_id:
        raise ValueError(f"No snapshot_id in response: {data}")
    deadline = time.time() + 300
    while time.time() < deadline:
        r = requests.get(f"{BRIGHT_DATA_BASE}/progress/{snapshot_id}",
                         headers=_bright_data_headers(api_key), timeout=15)
        r.raise_for_status()
        status = r.json().get("status", "")
        if status == "ready":
            break
        if status in ("failed", "error"):
            raise RuntimeError(f"Snapshot {snapshot_id} failed")
        time.sleep(5)
    else:
        raise TimeoutError(f"Snapshot {snapshot_id} not ready after 300s")
    r = requests.get(f"{BRIGHT_DATA_BASE}/snapshot/{snapshot_id}",
                     params={"format": "json"},
                     headers=_bright_data_headers(api_key), timeout=60)
    r.raise_for_status()
    return r.json()


def scrape_profile(username: str, api_key=None) -> Profile:
    api_key = api_key or os.getenv("BRIGHT_DATA_API_KEY", "")
    if not api_key:
        raise ValueError("BRIGHT_DATA_API_KEY is not set")
    items = _scrape_and_wait(username, api_key)
    profile = Profile(username=username)
    posts: list[Post] = []
    profile_data = None
    post_items = []
    for item in items:
        if item.get("followers") is not None and not item.get("post_url"):
            profile_data = item
        else:
            post_items.append(item)
    if profile_data:
        profile.username = profile_data.get("username", username)
        profile.full_name = profile_data.get("full_name", "") or profile_data.get("name", "")
        profile.followers = profile_data.get("followers", 0) or 0
        profile.following = profile_data.get("following", 0) or 0
        profile.bio = profile_data.get("biography", "") or profile_data.get("bio", "") or ""
        profile.category = profile_data.get("category", "") or "Creator"
        profile.posts_count = profile_data.get("posts", 0) or profile_data.get("media_count", 0) or 0
        profile.profile_pic_url = profile_data.get("profile_pic_url", "") or ""
    for item in post_items:
        p = Post()
        p.url = item.get("post_url", "") or item.get("url", "")
        raw_type = (item.get("type", "") or item.get("media_type", "") or "").lower()
        if raw_type in ("video", "reel", "clips") or "reel" in p.url.lower() or item.get("is_video"):
            p.type = "reel"
        else:
            p.type = "image"
        p.views = item.get("video_view_count", 0) or item.get("views", 0) or 0
        p.likes = item.get("likes", 0) or 0
        p.comments = item.get("comments", 0) or 0
        p.timestamp = item.get("timestamp", "") or item.get("date_posted", "") or ""
        caption_raw = item.get("description", "") or item.get("caption", "") or ""
        raw_tags = item.get("hashtags") or []
        if raw_tags:
            p.hashtags = [f"#{t}" if not t.startswith("#") else t for t in raw_tags]
        else:
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
        "data_sources": ["bright_data"],
    }
    _compute_analytics(profile)
    return profile

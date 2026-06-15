import os
import re
import time
import requests
from dataclasses import dataclass, field
from datetime import datetime

BRIGHT_DATA_BASE    = "https://api.brightdata.com/datasets/v3"
BRIGHT_DATA_PROFILE_DS = os.getenv("BRIGHT_DATA_DATASET_ID", "gd_l1vikfch901nx3by4")
BRIGHT_DATA_POSTS_DS   = "gd_lk5ns7kz21pck8jpis"

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
    engagement_rates = [(p.likes + p.comments) / followers * 100 for p in posts]
    profile.avg_engagement_rate = round(sum(engagement_rates) / len(engagement_rates), 2)
    day_counts = {}
    for p in posts:
        if p.timestamp:
            try:
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
            span = max(1, (max(timestamps) - min(timestamps)).days)
            profile.posting_frequency_per_week = round(len(posts) / span * 7, 1)
    reel_count = sum(1 for p in posts if p.type in ("reel", "video"))
    profile.top_format = "Reels" if reel_count >= len(posts) - reel_count else "Images"
    reel_views = [p.views for p in posts if p.type in ("reel", "video") and p.views]
    profile.meta["avg_reel_views"] = round(sum(reel_views) / len(reel_views)) if reel_views else 0
    half = len(posts) // 2
    if half > 0:
        recent = sum(engagement_rates[:half]) / half
        older  = sum(engagement_rates[half:]) / max(1, len(posts) - half)
        if recent > older * 1.1:
            profile.engagement_trend = "growing"
        elif recent < older * 0.9:
            profile.engagement_trend = "declining"

def _fetch_bright_data(username, api_key):
    profile_url = f"https://www.instagram.com/{username}"
    endpoint = f"{BRIGHT_DATA_BASE}/scrape?dataset_id={BRIGHT_DATA_PROFILE_DS}&format=json&include_errors=true"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = requests.post(endpoint, json=[{"url": profile_url}], headers=headers, timeout=45)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "snapshot_id" in data:
        return _poll_snapshot(data["snapshot_id"], api_key)
    if isinstance(data, dict):
        return data.get("results", data.get("data", [data]))
    return []

def _poll_snapshot(snapshot_id, api_key, max_wait=90):
    url = f"{BRIGHT_DATA_BASE}/snapshot/{snapshot_id}?format=json"
    headers = {"Authorization": f"Bearer {api_key}"}
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else data.get("results", data.get("data", []))
            if resp.status_code != 202:
                break
        except Exception:
            pass
        time.sleep(5)
    return []

def _parse_items(items, username):
    profile_item = None
    post_items = []
    for item in items:
        if item.get("followers") is not None and not item.get("post_url"):
            profile_item = item
        else:
            post_items.append(item)
    return profile_item, post_items

def _build_post(item):
    p = Post()
    p.url = item.get("post_url", "") or item.get("url", "") or ""
    raw_type = (item.get("type", "") or item.get("media_type", "") or "").lower()
    if raw_type in ("video", "reel", "clips") or "reel" in p.url.lower() or item.get("is_video"):
        p.type = "reel"
    p.views    = item.get("video_view_count") or item.get("view_count") or item.get("views") or item.get("play_count") or 0
    p.likes    = item.get("like_count") or item.get("likes") or 0
    p.comments = item.get("comments_count") or item.get("comments") or 0
    p.timestamp = item.get("timestamp") or item.get("date_posted") or item.get("taken_at") or ""
    caption_raw = item.get("caption") or item.get("description") or ""
    raw_tags = item.get("hashtags") or []
    p.hashtags = ([f"#{t}" if not str(t).startswith("#") else t for t in raw_tags]
                  if raw_tags else re.findall(r"#\w+", caption_raw))
    p.caption = caption_raw
    return p

def scrape_profile(username, api_key=None):
    api_key = api_key or os.getenv("BRIGHT_DATA_API_KEY", "")
    if not api_key:
        raise ValueError("BRIGHT_DATA_API_KEY is not set")
    raw_items = _fetch_bright_data(username, api_key)
    profile = Profile(username=username)
    profile_item, post_items = _parse_items(raw_items, username)
    if profile_item:
        profile.username        = profile_item.get("username", username)
        profile.full_name       = profile_item.get("full_name") or profile_item.get("name") or ""
        profile.followers       = profile_item.get("followers") or 0
        profile.following       = profile_item.get("following") or 0
        profile.bio             = profile_item.get("biography") or profile_item.get("bio") or ""
        profile.category        = profile_item.get("category") or "Creator"
        profile.posts_count     = profile_item.get("posts") or profile_item.get("media_count") or 0
        profile.profile_pic_url = profile_item.get("profile_pic_url") or ""
    seen = set()
    posts = []
    for item in post_items:
        if len(posts) >= 15:
            break
        url = item.get("post_url", "") or item.get("url", "")
        if url and url in seen:
            continue
        seen.add(url)
        posts.append(_build_post(item))
    profile.posts = posts
    reels_n = sum(1 for p in posts if p.type in ("reel", "video"))
    all_tags = {t for p in posts for t in p.hashtags}
    profile.meta = {
        "posts_scraped": len(posts), "reels_scraped": reels_n,
        "images_scraped": len(posts) - reels_n, "hashtags_analyzed": len(all_tags),
        "scrape_quality": "high" if len(posts) >= 12 else "medium" if len(posts) >= 6 else "low",
        "data_sources": ["bright_data"],
    }
    _compute_analytics(profile)
    return profile

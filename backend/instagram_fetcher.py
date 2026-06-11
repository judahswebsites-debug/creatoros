import instaloader
from dataclasses import dataclass, field
from typing import Optional
import re
import os
from collections import Counter

SESSION_FILE = os.path.join(os.path.dirname(__file__), ".ig_session")
_loader_instance: Optional[instaloader.Instaloader] = None


def get_loader() -> instaloader.Instaloader:
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
        )
        if os.path.exists(SESSION_FILE):
            try:
                _loader_instance.load_session_from_file("", SESSION_FILE)
            except Exception:
                pass
    return _loader_instance


def login(username: str, password: str) -> str:
    global _loader_instance
    L = instaloader.Instaloader(quiet=True)
    L.login(username, password)
    L.save_session_to_file(SESSION_FILE)
    _loader_instance = None  # reset so next fetch uses new session
    return "ok"


def is_logged_in() -> bool:
    return os.path.exists(SESSION_FILE)


@dataclass
class PostData:
    shortcode: str
    caption: str
    likes: int
    comments: int
    hashtags: list[str]
    mentions: list[str]
    is_video: bool
    video_views: Optional[int]
    timestamp: str
    url: str


@dataclass
class ProfileData:
    username: str
    full_name: str
    biography: str
    followers: int
    following: int
    post_count: int
    is_verified: bool
    posts: list[PostData] = field(default_factory=list)


def fetch_profile(username: str, max_posts: int = 30) -> ProfileData:
    L = get_loader()
    profile = instaloader.Profile.from_username(L.context, username)

    profile_data = ProfileData(
        username=profile.username,
        full_name=profile.full_name,
        biography=profile.biography,
        followers=profile.followers,
        following=profile.followees,
        post_count=profile.mediacount,
        is_verified=profile.is_verified,
    )

    posts_fetched = 0
    for post in profile.get_posts():
        if posts_fetched >= max_posts:
            break

        caption = post.caption or ""
        hashtags = list(post.caption_hashtags) if post.caption_hashtags else []
        mentions = list(post.caption_mentions) if post.caption_mentions else []

        profile_data.posts.append(PostData(
            shortcode=post.shortcode,
            caption=caption[:500],
            likes=post.likes,
            comments=post.comments,
            hashtags=hashtags,
            mentions=mentions,
            is_video=post.is_video,
            video_views=post.video_view_count if post.is_video else None,
            timestamp=post.date_utc.isoformat(),
            url=f"https://www.instagram.com/p/{post.shortcode}/",
        ))
        posts_fetched += 1

    return profile_data


def compute_stats(profile: ProfileData) -> dict:
    if not profile.posts:
        return {}

    total_likes = sum(p.likes for p in profile.posts)
    total_comments = sum(p.comments for p in profile.posts)
    n = len(profile.posts)

    avg_likes = total_likes / n
    avg_comments = total_comments / n
    engagement_rate = ((avg_likes + avg_comments) / profile.followers * 100) if profile.followers else 0

    all_hashtags = [h for p in profile.posts for h in p.hashtags]
    top_hashtags = [tag for tag, _ in Counter(all_hashtags).most_common(20)]

    # Separate video and image posts
    videos = [p for p in profile.posts if p.is_video]
    images = [p for p in profile.posts if not p.is_video]

    avg_video_likes = sum(p.likes for p in videos) / len(videos) if videos else 0
    avg_image_likes = sum(p.likes for p in images) / len(images) if images else 0

    # Top performing posts
    top_posts = sorted(profile.posts, key=lambda p: p.likes + p.comments * 2, reverse=True)[:5]

    # Word frequency in captions (excluding hashtags and stopwords)
    stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
                 "of", "with", "is", "it", "this", "that", "i", "my", "we", "you", "be", "are"}
    caption_words = []
    for p in profile.posts:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', p.caption.lower())
        caption_words.extend([w for w in words if w not in stopwords])
    top_words = [word for word, _ in Counter(caption_words).most_common(20)]

    return {
        "avg_likes": round(avg_likes, 1),
        "avg_comments": round(avg_comments, 1),
        "engagement_rate": round(engagement_rate, 2),
        "top_hashtags": top_hashtags,
        "top_caption_words": top_words,
        "video_count": len(videos),
        "image_count": len(images),
        "avg_video_likes": round(avg_video_likes, 1),
        "avg_image_likes": round(avg_image_likes, 1),
        "top_posts": [
            {
                "url": p.url,
                "likes": p.likes,
                "comments": p.comments,
                "caption_preview": p.caption[:120],
                "is_video": p.is_video,
                "hashtags": p.hashtags[:5],
            }
            for p in top_posts
        ],
    }

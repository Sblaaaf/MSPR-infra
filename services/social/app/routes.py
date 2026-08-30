from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import execute_write, fetch_all, fetch_one

router = APIRouter()


# ── Models ────────────────────────────────────────────────────────────────

class PostCreate(BaseModel):
    user_id: int
    user_name: str
    content: str = Field(..., min_length=1, max_length=2000)


class CommentCreate(BaseModel):
    user_id: int
    user_name: str
    content: str = Field(..., min_length=1, max_length=1000)


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


# ── Posts ─────────────────────────────────────────────────────────────────

@router.get("/posts")
def get_feed(user_id: int | None = None, limit: int = 20, offset: int = 0):
    posts = fetch_all(
        """
        SELECT p.id, p.user_id, p.user_name, p.content, p.created_at,
               COUNT(DISTINCT l.id) AS likes_count,
               COUNT(DISTINCT c.id) AS comments_count,
               MAX(CASE WHEN l.user_id = :uid THEN 1 ELSE 0 END) AS liked_by_me
        FROM social_posts p
        LEFT JOIN social_likes l ON l.post_id = p.id
        LEFT JOIN social_comments c ON c.post_id = p.id
        GROUP BY p.id
        ORDER BY p.created_at DESC
        LIMIT :limit OFFSET :offset
        """,
        {"uid": user_id or 0, "limit": limit, "offset": offset},
    )
    for p in posts:
        p["liked_by_me"] = bool(p.get("liked_by_me"))
        p["created_at"] = _iso(p.get("created_at"))
    return posts


@router.get("/posts/{post_id}")
def get_post(post_id: int, user_id: int | None = None):
    post = fetch_one(
        """
        SELECT p.id, p.user_id, p.user_name, p.content, p.created_at,
               COUNT(DISTINCT l.id) AS likes_count,
               COUNT(DISTINCT c.id) AS comments_count,
               MAX(CASE WHEN l.user_id = :uid THEN 1 ELSE 0 END) AS liked_by_me
        FROM social_posts p
        LEFT JOIN social_likes l ON l.post_id = p.id
        LEFT JOIN social_comments c ON c.post_id = p.id
        WHERE p.id = :post_id
        GROUP BY p.id
        """,
        {"post_id": post_id, "uid": user_id or 0},
    )
    if not post:
        raise HTTPException(status_code=404, detail="Publication introuvable.")
    post["liked_by_me"] = bool(post.get("liked_by_me"))
    post["created_at"] = _iso(post.get("created_at"))
    return post


@router.post("/posts", status_code=201)
def create_post(payload: PostCreate):
    result = execute_write(
        """
        INSERT INTO social_posts (user_id, user_name, content)
        VALUES (:user_id, :user_name, :content)
        RETURNING id, created_at
        """,
        {"user_id": payload.user_id, "user_name": payload.user_name, "content": payload.content},
    )
    row = result.mappings().first()
    return {"id": row["id"], "created_at": _iso(row["created_at"])}


@router.delete("/posts/{post_id}")
def delete_post(post_id: int, user_id: int):
    post = fetch_one("SELECT user_id FROM social_posts WHERE id = :id", {"id": post_id})
    if not post:
        raise HTTPException(status_code=404, detail="Publication introuvable.")
    if post["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Non autorisé.")
    execute_write("DELETE FROM social_posts WHERE id = :id", {"id": post_id})
    return {"success": True}


@router.get("/users/{user_id}/posts")
def get_user_posts(user_id: int):
    posts = fetch_all(
        """
        SELECT p.id, p.user_id, p.user_name, p.content, p.created_at,
               COUNT(DISTINCT l.id) AS likes_count,
               COUNT(DISTINCT c.id) AS comments_count
        FROM social_posts p
        LEFT JOIN social_likes l ON l.post_id = p.id
        LEFT JOIN social_comments c ON c.post_id = p.id
        WHERE p.user_id = :user_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
        """,
        {"user_id": user_id},
    )
    for p in posts:
        p["created_at"] = _iso(p.get("created_at"))
    return posts


# ── Likes ─────────────────────────────────────────────────────────────────

@router.post("/posts/{post_id}/like")
def toggle_like(post_id: int, user_id: int):
    if not fetch_one("SELECT id FROM social_posts WHERE id = :id", {"id": post_id}):
        raise HTTPException(status_code=404, detail="Publication introuvable.")
    existing = fetch_one(
        "SELECT id FROM social_likes WHERE post_id = :post_id AND user_id = :user_id",
        {"post_id": post_id, "user_id": user_id},
    )
    if existing:
        execute_write(
            "DELETE FROM social_likes WHERE post_id = :post_id AND user_id = :user_id",
            {"post_id": post_id, "user_id": user_id},
        )
        return {"liked": False}
    execute_write(
        "INSERT INTO social_likes (post_id, user_id) VALUES (:post_id, :user_id)",
        {"post_id": post_id, "user_id": user_id},
    )
    return {"liked": True}


# ── Comments ──────────────────────────────────────────────────────────────

@router.get("/posts/{post_id}/comments")
def get_comments(post_id: int):
    comments = fetch_all(
        """
        SELECT id, user_id, user_name, content, created_at
        FROM social_comments
        WHERE post_id = :post_id
        ORDER BY created_at ASC
        """,
        {"post_id": post_id},
    )
    for c in comments:
        c["created_at"] = _iso(c.get("created_at"))
    return comments


@router.post("/posts/{post_id}/comments", status_code=201)
def add_comment(post_id: int, payload: CommentCreate):
    if not fetch_one("SELECT id FROM social_posts WHERE id = :id", {"id": post_id}):
        raise HTTPException(status_code=404, detail="Publication introuvable.")
    result = execute_write(
        """
        INSERT INTO social_comments (post_id, user_id, user_name, content)
        VALUES (:post_id, :user_id, :user_name, :content)
        RETURNING id, created_at
        """,
        {"post_id": post_id, "user_id": payload.user_id,
         "user_name": payload.user_name, "content": payload.content},
    )
    row = result.mappings().first()
    return {"id": row["id"], "created_at": _iso(row["created_at"])}


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, user_id: int):
    comment = fetch_one("SELECT user_id FROM social_comments WHERE id = :id", {"id": comment_id})
    if not comment:
        raise HTTPException(status_code=404, detail="Commentaire introuvable.")
    if comment["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Non autorisé.")
    execute_write("DELETE FROM social_comments WHERE id = :id", {"id": comment_id})
    return {"success": True}

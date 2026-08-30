import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import routes
from main import app


class DummyResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


client = TestClient(app)


def _post_row(post_id: int = 1, user_id: int = 976, likes: int = 0, comments: int = 0, liked: int = 0) -> dict:
    return {
        "id": post_id,
        "user_id": user_id,
        "user_name": "Camille",
        "content": "Ma premiere publication !",
        "created_at": datetime.now(),
        "likes_count": likes,
        "comments_count": comments,
        "liked_by_me": liked,
    }


def _comment_row(comment_id: int = 1, post_id: int = 1, user_id: int = 976) -> dict:
    return {
        "id": comment_id,
        "post_id": post_id,
        "user_id": user_id,
        "user_name": "Camille",
        "content": "Super repas !",
        "created_at": datetime.now(),
    }


# ---------------------------------------------------------------------------
# GET /posts
# ---------------------------------------------------------------------------

def test_get_feed(monkeypatch):
    monkeypatch.setattr(routes, "fetch_all", lambda *a, **kw: [_post_row()])

    resp = client.get("/posts", params={"user_id": 976})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["user_name"] == "Camille"
    assert body[0]["liked_by_me"] is False


def test_get_feed_empty(monkeypatch):
    monkeypatch.setattr(routes, "fetch_all", lambda *a, **kw: [])

    resp = client.get("/posts")

    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /posts/{id}
# ---------------------------------------------------------------------------

def test_get_post_found(monkeypatch):
    monkeypatch.setattr(routes, "fetch_one", lambda *a, **kw: _post_row())

    resp = client.get("/posts/1")

    assert resp.status_code == 200
    assert resp.json()["id"] == 1


def test_get_post_not_found(monkeypatch):
    monkeypatch.setattr(routes, "fetch_one", lambda *a, **kw: None)

    resp = client.get("/posts/999")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /posts
# ---------------------------------------------------------------------------

def test_create_post(monkeypatch):
    monkeypatch.setattr(
        routes, "execute_write",
        lambda *a, **kw: DummyResult({"id": 1, "created_at": datetime.now()}),
    )

    resp = client.post("/posts", json={"user_id": 976, "user_name": "Camille", "content": "Hello"})

    assert resp.status_code == 201
    assert resp.json()["id"] == 1


def test_create_post_empty_content_rejected():
    resp = client.post("/posts", json={"user_id": 976, "user_name": "Camille", "content": ""})
    assert resp.status_code == 422


def test_create_post_missing_fields():
    resp = client.post("/posts", json={"content": "Hello"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /posts/{id}
# ---------------------------------------------------------------------------

def test_delete_post_owner(monkeypatch):
    monkeypatch.setattr(routes, "fetch_one", lambda *a, **kw: {"user_id": 976})
    monkeypatch.setattr(routes, "execute_write", lambda *a, **kw: None)

    resp = client.request("DELETE", "/posts/1", params={"user_id": 976})

    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_delete_post_not_owner(monkeypatch):
    monkeypatch.setattr(routes, "fetch_one", lambda *a, **kw: {"user_id": 976})

    resp = client.request("DELETE", "/posts/1", params={"user_id": 1})

    assert resp.status_code == 403


def test_delete_post_not_found(monkeypatch):
    monkeypatch.setattr(routes, "fetch_one", lambda *a, **kw: None)

    resp = client.request("DELETE", "/posts/999", params={"user_id": 976})

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /posts/{id}/like
# ---------------------------------------------------------------------------

def test_like_post_new(monkeypatch):
    calls = {"n": 0}

    def fake_fetch_one(query, *a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"id": 1}  # post exists
        return None  # no existing like

    monkeypatch.setattr(routes, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(routes, "execute_write", lambda *a, **kw: None)

    resp = client.post("/posts/1/like", params={"user_id": 976})

    assert resp.status_code == 200
    assert resp.json()["liked"] is True


def test_unlike_post_existing(monkeypatch):
    calls = {"n": 0}

    def fake_fetch_one(query, *a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"id": 1}  # post exists
        return {"id": 5}  # existing like

    monkeypatch.setattr(routes, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(routes, "execute_write", lambda *a, **kw: None)

    resp = client.post("/posts/1/like", params={"user_id": 976})

    assert resp.status_code == 200
    assert resp.json()["liked"] is False


def test_like_post_not_found(monkeypatch):
    monkeypatch.setattr(routes, "fetch_one", lambda *a, **kw: None)

    resp = client.post("/posts/999/like", params={"user_id": 976})

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET/POST /posts/{id}/comments
# ---------------------------------------------------------------------------

def test_get_comments(monkeypatch):
    monkeypatch.setattr(routes, "fetch_all", lambda *a, **kw: [_comment_row()])

    resp = client.get("/posts/1/comments")

    assert resp.status_code == 200
    assert resp.json()[0]["content"] == "Super repas !"


def test_add_comment(monkeypatch):
    monkeypatch.setattr(routes, "fetch_one", lambda *a, **kw: {"id": 1})
    monkeypatch.setattr(
        routes, "execute_write",
        lambda *a, **kw: DummyResult({"id": 1, "created_at": datetime.now()}),
    )

    resp = client.post(
        "/posts/1/comments",
        json={"user_id": 976, "user_name": "Camille", "content": "Super repas !"},
    )

    assert resp.status_code == 201


def test_add_comment_post_not_found(monkeypatch):
    monkeypatch.setattr(routes, "fetch_one", lambda *a, **kw: None)

    resp = client.post(
        "/posts/999/comments",
        json={"user_id": 976, "user_name": "Camille", "content": "Hello"},
    )

    assert resp.status_code == 404


def test_add_comment_empty_content_rejected():
    resp = client.post(
        "/posts/1/comments",
        json={"user_id": 976, "user_name": "Camille", "content": ""},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /comments/{id}
# ---------------------------------------------------------------------------

def test_delete_comment_owner(monkeypatch):
    monkeypatch.setattr(routes, "fetch_one", lambda *a, **kw: {"user_id": 976})
    monkeypatch.setattr(routes, "execute_write", lambda *a, **kw: None)

    resp = client.request("DELETE", "/comments/1", params={"user_id": 976})

    assert resp.status_code == 200


def test_delete_comment_not_owner(monkeypatch):
    monkeypatch.setattr(routes, "fetch_one", lambda *a, **kw: {"user_id": 976})

    resp = client.request("DELETE", "/comments/1", params={"user_id": 1})

    assert resp.status_code == 403


def test_delete_comment_not_found(monkeypatch):
    monkeypatch.setattr(routes, "fetch_one", lambda *a, **kw: None)

    resp = client.request("DELETE", "/comments/999", params={"user_id": 976})

    assert resp.status_code == 404

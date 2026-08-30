import os

from sqlalchemy import create_engine, text

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "healthai"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}


def get_engine():
    url = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )
    return create_engine(url, echo=False, future=True, pool_pre_ping=True)


engine = get_engine()


def fetch_all(query: str, params: dict | None = None) -> list[dict]:
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return [dict(row) for row in result.mappings()]


def fetch_one(query: str, params: dict | None = None) -> dict | None:
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        row = result.mappings().first()
        return dict(row) if row else None


def execute_write(query: str, params: dict | None = None):
    with engine.begin() as conn:
        return conn.execute(text(query), params or {})


def init_schema():
    schema = """
    CREATE TABLE IF NOT EXISTS social_posts (
        id          SERIAL PRIMARY KEY,
        user_id     INTEGER NOT NULL,
        user_name   VARCHAR(255),
        content     TEXT NOT NULL,
        created_at  TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS social_likes (
        id          SERIAL PRIMARY KEY,
        post_id     INTEGER NOT NULL REFERENCES social_posts(id) ON DELETE CASCADE,
        user_id     INTEGER NOT NULL,
        created_at  TIMESTAMP DEFAULT NOW(),
        UNIQUE(post_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS social_comments (
        id          SERIAL PRIMARY KEY,
        post_id     INTEGER NOT NULL REFERENCES social_posts(id) ON DELETE CASCADE,
        user_id     INTEGER NOT NULL,
        user_name   VARCHAR(255),
        content     TEXT NOT NULL,
        created_at  TIMESTAMP DEFAULT NOW()
    );
    """
    with engine.begin() as conn:
        for stmt in schema.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from config import settings
from contextlib import contextmanager
import threading
from typing import Generator

# Sharding konfigürasyonu
SHARD_COUNT = 2
shard_engines = {}
local = threading.local()

def get_shard_key(video_id: str) -> int:
    """Video ID'sine göre shard belirle"""
    return hash(video_id) % SHARD_COUNT

def create_shard_engine(shard_id: int):
    """Shard için database engine oluştur"""
    db_url = f"{settings.DATABASE_URL}_{shard_id}"
    return create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
        echo=settings.DEBUG
    )

# Her shard için engine oluştur
for shard_id in range(SHARD_COUNT):
    shard_engines[shard_id] = create_shard_engine(shard_id)

# Base model class
Base = declarative_base()

# Her shard için metadata
shard_metadata = {
    shard_id: MetaData() for shard_id in range(SHARD_COUNT)
}

def get_engine(video_id: str = None):
    """Video ID'sine göre doğru shard'ı seç"""
    if video_id:
        shard_id = get_shard_key(video_id)
    else:
        shard_id = getattr(local, 'shard_id', 0)
    return shard_engines[shard_id]

def get_metadata(video_id: str = None):
    """Video ID'sine göre doğru metadata'yı seç"""
    if video_id:
        shard_id = get_shard_key(video_id)
    else:
        shard_id = getattr(local, 'shard_id', 0)
    return shard_metadata[shard_id]

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=get_engine()
)

@contextmanager
def get_db(video_id: str = None) -> Generator:
    """Database session context manager"""
    if video_id:
        local.shard_id = get_shard_key(video_id)
    
    db = scoped_session(
        sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(video_id)
        )
    )
    try:
        yield db
    finally:
        db.remove()

def init_db():
    """Tüm shard'ları initialize et"""
    for shard_id in range(SHARD_COUNT):
        engine = shard_engines[shard_id]
        Base.metadata.create_all(bind=engine)

def get_all_sessions():
    """Tüm shard'lar için session oluştur"""
    sessions = []
    for shard_id in range(SHARD_COUNT):
        engine = shard_engines[shard_id]
        session = sessionmaker(bind=engine)()
        sessions.append(session)
    return sessions 
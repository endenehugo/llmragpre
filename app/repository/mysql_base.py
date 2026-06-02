from __future__ import annotations

from dataclasses import dataclass

from flask import current_app
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker


Base = declarative_base()


@dataclass
class DatabaseManager:
    _engine = None
    _session_factory = None
    _config_fingerprint = None
    _tables_ready = False

    @classmethod
    def _build_config_fingerprint(cls, config: dict) -> tuple:
        return (
            config.get("MYSQL_HOST"),
            config.get("MYSQL_PORT"),
            config.get("MYSQL_USER"),
            config.get("MYSQL_PASSWORD"),
            config.get("MYSQL_DATABASE"),
            config.get("MYSQL_CHARSET"),
            config.get("MYSQL_POOL_SIZE"),
            config.get("MYSQL_POOL_RECYCLE"),
        )

    @classmethod
    def _build_url(cls, config: dict) -> str:
        return (
            f"mysql+pymysql://{config['MYSQL_USER']}:{config['MYSQL_PASSWORD']}"
            f"@{config['MYSQL_HOST']}:{config['MYSQL_PORT']}/{config['MYSQL_DATABASE']}"
            f"?charset={config.get('MYSQL_CHARSET', 'utf8mb4')}"
        )

    @classmethod
    def _ensure_engine(cls):
        config = current_app.config
        fingerprint = cls._build_config_fingerprint(config)
        if cls._engine is not None and cls._config_fingerprint == fingerprint:
            return

        engine = create_engine(
            cls._build_url(config),
            pool_pre_ping=True,
            pool_recycle=config.get("MYSQL_POOL_RECYCLE", 3600),
            pool_size=config.get("MYSQL_POOL_SIZE", 5),
            future=True,
        )
        cls._engine = engine
        cls._session_factory = scoped_session(
            sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        )
        cls._config_fingerprint = fingerprint
        cls._tables_ready = False

    @classmethod
    def ensure_tables(cls):
        cls._ensure_engine()
        if cls._tables_ready:
            return
        Base.metadata.create_all(bind=cls._engine)
        cls._tables_ready = True

    @classmethod
    def get_session(cls):
        cls.ensure_tables()
        return cls._session_factory()
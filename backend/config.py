import os


def db_path() -> str:
    return os.getenv("DATABASE_PATH", "/mnt/media/metadata.db")


def media_path() -> str:
    return os.getenv("MEDIA_PATH", "/mnt/media")


def models_path() -> str:
    return os.getenv("MODELS_PATH", "/app/models")

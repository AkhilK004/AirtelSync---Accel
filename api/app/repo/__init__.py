from functools import lru_cache

from app.config import settings
from app.repo.memory import MemoryRepo


@lru_cache(maxsize=1)
def get_repo():
    if settings.STORAGE == "firestore":
        from app.repo.firestore import FirestoreRepo

        return FirestoreRepo()
    return MemoryRepo()

from typing import List

from features.saved_filters import repository
from features.saved_filters.schemas import SavedFilterCreate


def list_saved_filters(user_id: int) -> List[dict]:
    return repository.list_for_user(user_id)


def create_saved_filter(user_id: int, data: SavedFilterCreate) -> dict:
    # Drop keys the user left unset so the stored object stays tidy.
    filters = data.filters.model_dump(exclude_none=True)
    return repository.create(user_id, data.name.strip(), filters)


def delete_saved_filter(user_id: int, filter_id: int) -> bool:
    return repository.remove(user_id, filter_id)

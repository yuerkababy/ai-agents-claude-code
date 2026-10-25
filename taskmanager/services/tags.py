from utils.errors import ValidationError

TAGS: dict[int, dict] = {}

def create_tag(name: str) -> dict:
    """Create a new tag.

    Args:
        name: The tag's name.

    Returns:
        The newly created tag record.

    Raises:
        ValidationError: If name is empty or not a string.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name", "cannot be empty")
    new_id = max(TAGS.keys(), default=0) + 1
    TAGS[new_id] = {"id": new_id, "name": name}
    return TAGS[new_id]

from utils.errors import NotFoundError, ValidationError

NOTIFICATION_PREFS = ("email", "sms", "none")

USERS: dict[int, dict] = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com", "notification_pref": None},
    2: {"id": 2, "name": "Bob",   "email": "bob@example.com",   "notification_pref": None},
}

def get_user(user_id: int) -> dict:
    """Retrieve a user by ID.

    Args:
        user_id: The unique identifier for the user.

    Returns:
        The user record as a dictionary.

    Raises:
        NotFoundError: If no user exists with the given ID.
    """
    if user_id not in USERS:
        raise NotFoundError("User")
    return USERS[user_id]

def create_user(name: str, email: str) -> dict:
    """Create a new user.

    Args:
        name: The user's display name.
        email: The user's email address.

    Returns:
        The newly created user record.

    Raises:
        ValidationError: If name or email is empty or not a string.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name", "cannot be empty")
    if not isinstance(email, str) or "@" not in email:
        raise ValidationError("email", "must be a valid email address")
    new_id = max(USERS.keys(), default=0) + 1
    USERS[new_id] = {"id": new_id, "name": name, "email": email, "notification_pref": None}
    return USERS[new_id]

def list_users() -> list[dict]:
    """List all users.

    Returns:
        A list of every user record.
    """
    return list(USERS.values())

def get_notification_pref(user_id: int) -> str | None:
    """Retrieve a user's notification preference.

    Args:
        user_id: The unique identifier for the user.

    Returns:
        The user's notification preference ("email" or "sms"), or None if unset or opted out.

    Raises:
        NotFoundError: If no user exists with the given ID.
    """
    if user_id not in USERS:
        raise NotFoundError("User")
    return USERS[user_id]["notification_pref"]

def set_notification_pref(user_id: int, pref: str) -> dict:
    """Set a user's notification preference.

    Args:
        user_id: The unique identifier for the user.
        pref: One of NOTIFICATION_PREFS. "none" is stored as None.

    Returns:
        The updated user record.

    Raises:
        NotFoundError: If no user exists with the given ID.
        ValidationError: If pref is not one of NOTIFICATION_PREFS.
    """
    if user_id not in USERS:
        raise NotFoundError("User")
    if pref not in NOTIFICATION_PREFS:
        raise ValidationError("notification_pref", "must be one of: email, sms, none")
    USERS[user_id]["notification_pref"] = None if pref == "none" else pref
    return USERS[user_id]

import pytest

from app import app
from services.users import create_user, get_notification_pref, set_notification_pref
from utils.errors import NotFoundError, ValidationError

def test_notification_pref_defaults_to_none():
    user = create_user("Dana", "dana@example.com")
    assert get_notification_pref(user["id"]) is None

@pytest.mark.parametrize("pref", ["email", "sms"])
def test_set_notification_pref_valid(pref):
    user = create_user("Eve", "eve@example.com")
    updated = set_notification_pref(user["id"], pref)
    assert updated["notification_pref"] == pref
    assert get_notification_pref(user["id"]) == pref

def test_set_notification_pref_none_reads_back_as_none():
    user = create_user("Frank", "frank@example.com")
    set_notification_pref(user["id"], "email")
    updated = set_notification_pref(user["id"], "none")
    assert updated["notification_pref"] is None
    assert get_notification_pref(user["id"]) is None

def test_set_notification_pref_invalid_raises_validation_error():
    user = create_user("Grace", "grace@example.com")
    with pytest.raises(ValidationError):
        set_notification_pref(user["id"], "pigeon")

def test_get_notification_pref_unknown_user_raises_not_found():
    with pytest.raises(NotFoundError):
        get_notification_pref(999)

def test_set_notification_pref_unknown_user_raises_not_found():
    with pytest.raises(NotFoundError):
        set_notification_pref(999, "email")

def test_list_users_route_includes_notification_pref():
    response = app.test_client().get("/api/users")
    assert response.status_code == 200
    for user in response.get_json():
        assert "notification_pref" in user

def test_get_user_route_includes_notification_pref():
    response = app.test_client().get("/api/users/1")
    assert response.status_code == 200
    assert "notification_pref" in response.get_json()

def test_set_notification_pref_route_valid():
    user = create_user("Heidi", "heidi@example.com")
    response = app.test_client().patch(
        f"/api/users/{user['id']}/notifications", json={"notification_pref": "sms"}
    )
    assert response.status_code == 200
    assert response.get_json()["notification_pref"] == "sms"

def test_set_notification_pref_route_invalid_value_returns_422():
    response = app.test_client().patch(
        "/api/users/1/notifications", json={"notification_pref": "pigeon"}
    )
    assert response.status_code == 422
    assert response.get_json() == {
        "error": "Invalid notification_pref: must be one of: email, sms, none"
    }

def test_set_notification_pref_route_missing_key_returns_422():
    response = app.test_client().patch("/api/users/1/notifications", json={})
    assert response.status_code == 422

def test_set_notification_pref_route_unknown_user_returns_404():
    response = app.test_client().patch(
        "/api/users/999/notifications", json={"notification_pref": "email"}
    )
    assert response.status_code == 404
    assert response.get_json() == {"error": "User not found"}

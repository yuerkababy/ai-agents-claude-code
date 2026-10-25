from app import app
from services.tasks import create_task

def test_list_tasks_route_non_numeric_priority_returns_422():
    response = app.test_client().get("/api/tasks?priority=abc")
    assert response.status_code == 422
    assert response.get_json() == {"error": "Invalid priority: must be an integer from 1 to 5"}

def test_update_task_route_valid():
    created = create_task("Paint fence", 1, priority=3)
    response = app.test_client().patch(f"/api/tasks/{created['id']}", json={"priority": 2})
    assert response.status_code == 200
    assert response.get_json()["priority"] == 2

def test_update_task_route_missing_task_returns_404():
    response = app.test_client().patch("/api/tasks/999", json={"priority": 2})
    assert response.status_code == 404

def test_update_task_route_invalid_priority_returns_422():
    response = app.test_client().patch("/api/tasks/1", json={"priority": 9})
    assert response.status_code == 422
    assert response.get_json() == {"error": "Invalid priority: must be an integer from 1 to 5"}

def test_update_task_route_empty_body_returns_422():
    response = app.test_client().patch("/api/tasks/1", json={})
    assert response.status_code == 422

def test_create_task_route_default_priority():
    response = app.test_client().post("/api/tasks", json={"title": "Water plants", "user_id": 1})
    assert response.status_code == 201
    assert response.get_json()["priority"] == 3

def test_create_task_route_explicit_priority():
    response = app.test_client().post(
        "/api/tasks", json={"title": "Pay rent", "user_id": 1, "priority": 1}
    )
    assert response.status_code == 201
    assert response.get_json()["priority"] == 1

def test_create_task_route_invalid_priority_returns_422():
    response = app.test_client().post(
        "/api/tasks", json={"title": "Bad task", "user_id": 1, "priority": 9}
    )
    assert response.status_code == 422
    assert response.get_json() == {"error": "Invalid priority: must be an integer from 1 to 5"}

def test_get_task_route_includes_priority():
    response = app.test_client().get("/api/tasks/1")
    assert response.status_code == 200
    assert "priority" in response.get_json()

def test_list_tasks_route_filter_by_priority():
    client = app.test_client()
    low = client.post("/api/tasks", json={"title": "Low task", "user_id": 1, "priority": 5})
    urgent = client.post("/api/tasks", json={"title": "Urgent task", "user_id": 1, "priority": 1})
    response = client.get("/api/tasks?priority=5")
    assert response.status_code == 200
    ids = [task["id"] for task in response.get_json()]
    assert low.get_json()["id"] in ids
    assert urgent.get_json()["id"] not in ids

def test_create_task_route_default_estimate():
    response = app.test_client().post("/api/tasks", json={"title": "Sweep porch", "user_id": 1})
    assert response.status_code == 201
    assert response.get_json()["estimate"] == 1

def test_create_task_route_explicit_estimate():
    response = app.test_client().post(
        "/api/tasks", json={"title": "Fix sink", "user_id": 1, "estimate": 8}
    )
    assert response.status_code == 201
    assert response.get_json()["estimate"] == 8

def test_create_task_route_invalid_estimate_returns_422():
    response = app.test_client().post(
        "/api/tasks", json={"title": "Bad estimate", "user_id": 1, "estimate": 9}
    )
    assert response.status_code == 422
    assert response.get_json() == {"error": "Invalid estimate: must be an integer from 1 to 8"}

def test_get_task_route_includes_estimate():
    created = create_task("Clean garage", 1, estimate=3)
    response = app.test_client().get(f"/api/tasks/{created['id']}")
    assert response.status_code == 200
    assert response.get_json()["estimate"] == 3

def test_update_task_route_valid_estimate():
    created = create_task("Mow lawn", 1, priority=3, estimate=2)
    response = app.test_client().patch(
        f"/api/tasks/{created['id']}", json={"priority": 3, "estimate": 5}
    )
    assert response.status_code == 200
    assert response.get_json()["estimate"] == 5

def test_update_task_route_invalid_estimate_returns_422():
    created = create_task("Wash car", 1, priority=3, estimate=2)
    response = app.test_client().patch(
        f"/api/tasks/{created['id']}", json={"priority": 3, "estimate": 0}
    )
    assert response.status_code == 422
    assert response.get_json() == {"error": "Invalid estimate: must be an integer from 1 to 8"}

def test_update_task_route_null_estimate_returns_422():
    created = create_task("Rake leaves", 1, priority=3, estimate=2)
    response = app.test_client().patch(
        f"/api/tasks/{created['id']}", json={"priority": 3, "estimate": None}
    )
    assert response.status_code == 422

def test_list_tasks_route_filter_by_estimate():
    client = app.test_client()
    big = client.post("/api/tasks", json={"title": "Big task", "user_id": 1, "estimate": 7})
    small = client.post("/api/tasks", json={"title": "Small task", "user_id": 1, "estimate": 2})
    response = client.get("/api/tasks?estimate=7")
    assert response.status_code == 200
    ids = [task["id"] for task in response.get_json()]
    assert big.get_json()["id"] in ids
    assert small.get_json()["id"] not in ids

def test_list_tasks_route_non_numeric_estimate_returns_422():
    response = app.test_client().get("/api/tasks?estimate=abc")
    assert response.status_code == 422
    assert response.get_json() == {"error": "Invalid estimate: must be an integer from 1 to 8"}

def test_list_tasks_route_out_of_range_estimate_returns_422():
    response = app.test_client().get("/api/tasks?estimate=9")
    assert response.status_code == 422

def test_create_tag_route_valid():
    response = app.test_client().post("/api/tags", json={"name": "urgent"})
    assert response.status_code == 201
    assert response.get_json()["name"] == "urgent"

def test_create_tag_route_empty_name_returns_422():
    response = app.test_client().post("/api/tags", json={"name": "  "})
    assert response.status_code == 422
    assert response.get_json() == {"error": "Invalid name: cannot be empty"}

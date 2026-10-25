import pytest
from services.tasks import process_order, get_task, create_task, get_tasks_for_user
from services.tasks import list_tasks
from services.tasks import update_task
from utils.errors import NotFoundError, ValidationError

def test_process_order_valid():
    result = process_order(1)
    assert result["done"] is True

def test_process_order_invalid():
    with pytest.raises(Exception):
        process_order(999)

def test_get_task_valid():
    result = get_task(2)
    assert result["title"] == "Write report"

def test_get_task_invalid():
    with pytest.raises(Exception):
        get_task(999)

def test_get_task_missing_raises_not_found():
    with pytest.raises(NotFoundError):
        get_task(999)

def test_create_task_valid():
    result = create_task("Walk the dog", 1)
    assert result["title"] == "Walk the dog"
    assert result["done"] is False
    assert get_task(result["id"]) is result

def test_create_task_empty_title_raises_validation_error():
    with pytest.raises(ValidationError):
        create_task("   ", 1)

def test_get_tasks_for_user_valid():
    created = create_task("Water plants", 2)
    task_ids = [task["id"] for task in get_tasks_for_user(2)]
    assert created["id"] in task_ids
    assert 3 in task_ids
    assert 1 not in task_ids

def test_get_tasks_for_user_unknown_user_raises_not_found():
    with pytest.raises(NotFoundError):
        get_tasks_for_user(999)

def test_list_tasks_all():
    task_ids = [task["id"] for task in list_tasks()]
    assert {1, 2, 3} <= set(task_ids)

def test_list_tasks_filter_by_priority():
    task_ids = [task["id"] for task in list_tasks(5)]
    assert 3 in task_ids
    assert 1 not in task_ids
    assert 2 not in task_ids

def test_list_tasks_invalid_priority_raises_validation_error():
    for priority in (0, 6, True):
        with pytest.raises(ValidationError):
            list_tasks(priority)

def test_list_tasks_string_priority():
    task_ids = [task["id"] for task in list_tasks("5")]
    assert 3 in task_ids
    with pytest.raises(ValidationError):
        list_tasks("abc")

def test_update_task_valid():
    created = create_task("Fix bike", 1, priority=3)
    result = update_task(created["id"], 1)
    assert result["priority"] == 1
    assert get_task(created["id"])["priority"] == 1

def test_update_task_missing_raises_not_found():
    with pytest.raises(NotFoundError):
        update_task(999, 2)

def test_update_task_invalid_priority_raises_validation_error():
    created = create_task("Clean garage", 1, priority=4)
    for priority in (0, 6, True, "3", None):
        with pytest.raises(ValidationError):
            update_task(created["id"], priority)
    assert get_task(created["id"])["priority"] == 4

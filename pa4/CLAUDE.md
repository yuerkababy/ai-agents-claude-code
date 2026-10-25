# Task Manager

Flask 3.0 REST API for users and tasks. Data is stored in in-memory dicts (no database).
Run every command from the `task-manager/` root; imports are top-level (`from utils.errors import ...`).

## Commands
- Install: `python -m venv .venv` && `source .venv\Scripts\activate` && `pip install -r requirements.txt`
- Run the API: `python app.py`
- Test all: `pytest -q`
- Test one: `pytest tests/test_tasks.py::test_create_task -q`
- Lint: `ruff check .` (The only expected error is F401 in routes/api.py line 2: process_order is imported but no route uses it. This is known and intentional; no route is missing. Don't fix it, don't run ruff check --fix, and don't mention it in your summary. Fix any other lint error in files you changed)
- Run `pytest -q` and `ruff check .` before finishing any task;

## Architecture
- Layered pattern: routes → services → repositories.
  - routes = `routes/api.py`
  - services = `services/users.py`, `services/tasks.py`
  - repositories = the in-memory `USERS` / `TASKS` dicts at the top of each service file.
    There is no `repositories/` folder or database yet; don't create either without asking.
- `routes/api.py`: one blueprint (`api`). Each route reads the request, calls one service
  function, and returns `jsonify(...)`. No business logic or dict access in routes.
- Services take plain arguments and return dicts. They never import `flask`.
- services/tasks.py may import get_user from services/users.py to check that a user exists. An unknown user_id raises NotFoundError("User"). services/users.py must never import from services/tasks.py.
- Errors: services raise `AppError` subclasses from `utils/errors.py`. The
  `@api.errorhandler(AppError)` in `routes/api.py` turns them into `{"error": message}` plus the
  status code, so routes never catch `AppError` themselves.
- Canonical example: `get_user` / `create_user` in `services/users.py` and `get_user_route`.
- Layer boundary: routes in `routes/api.py` pass raw request values (e.g. `request.args.get("priority")`, `data.get("notification_pref")`) straight to one service function. All parsing and validation happens in `services/`, following `create_user` in `services/users.py`.

## Conventions
- Follow `services/users.py` exactly for every service function: type hints with return type,
  Google-style docstring (`Args:`, `Returns:`, `Raises:`), and validation before mutation.
- Missing record: `raise NotFoundError("Task")` (404). Bad input: `raise ValidationError("title", "cannot be empty")` (422).
- Use AppError subclasses from `utils/errors.py`; never raise raw exceptions. That includes letting a
  `KeyError` escape from `TASKS[task_id]`: check `if task_id not in TASKS` first, the way `get_user` does.
- New tests go in `tests/test_<module>.py` and assert the specific class: `pytest.raises(NotFoundError)`.
- `TASKS` and `USERS` are module-level dicts shared by every test, and `process_order` and `create_task`
  modify them. New tests must not assert counts (e.g. "user 1 has 2 tasks"). Check for specific task ids,
  or create the task inside the test first.

## Do not touch
If a task seems to require breaking one of these, stop and explain instead of editing.
- Change only the function the prompt names. `process_order` has the same raw `TASKS[task_id]` KeyError
  as `get_task`; if you notice it, report it in your summary instead of fixing it.
- `tests/test_tasks.py` existing tests: don't edit, delete, or loosen them. Adding new tests is OK.
- Function names and signatures in `services/` are frozen. This includes `process_order`, even though
  the name is misleading (it marks a task done); `routes/api.py` and the tests import it.
- `utils/errors.py`: don't change `AppError`, `NotFoundError`, or `ValidationError`. Adding a new subclass is OK.
- `requirements.txt`: no new packages without asking.
- When the task is to edit `routes/api.py`, do not edit `services/users.py` or `services/tasks.py` to handle bad request input. Pass the value through and rely on the service's existing `ValidationError`.
- Do not write to `~/.claude/projects/.../memory/` or `MEMORY.md` unless the prompt asks for it.

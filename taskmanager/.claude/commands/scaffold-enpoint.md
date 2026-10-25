## Goal
Scaffold a new API endpoint from $ARGUMENTS, which holds two values, the resource name first, then the HTTP method (example: tags POST).

Create or update exactly these files:
- Route file: routes/api.py (add one route to the existing api blueprint)
- Service file: services/<resource>.py
- Schema file: this project has no schemas/ folder. Input validation IS the schema, and it lives at the top of the service function, raising ValidationError. Do not create a schemas/ folder.
- Test file: tests/test_api.py (add an HTTP test for the new endpoint)

If $ARGUMENTS does not contain both a resource name and a method from GET, POST, PATCH, or DELETE, stop and ask instead of guessing.

## Context
- Canonical pattern: the task routes in routes/api.py, which play the role of routes/tasks.py in this project. All routes live in that one file. Copy how create_task_route reads the request, calls one service function, and returns jsonify(...).
- Canonical service pattern: create_task in services/tasks.py and create_user / get_user in services/users.py (type hints, Google-style docstring with Args/Returns/Raises, validation before mutation).
- Data is stored in a module-level dict at the top of each service file (like TASKS and USERS). There is no database.
- Errors: services raise AppError subclasses from utils/errors.py. The @api.errorhandler(AppError) in routes/api.py converts them, so routes never catch AppError.
- Status codes: POST that creates returns 201; GET and PATCH return 200; DELETE returns 204.

## Constraints
- No business logic in the route handler: no validation, no dict access, no if/else on data. The route only reads the request, calls ONE service function, and returns jsonify(...) with a status code.
- Services never import flask.
Do not create a new blueprint, a routes/<resource>.py file, a schemas/ folder, a repositories/ folder, or a database.
- Do not modify utils/errors.py, requirements.txt, or existing tests in tests/test_tasks.py. Do not change existing function names or signatures.
- New tests must not assert counts in shared dicts; create the data inside the test.
## Verification
- Add an HTTP test in tests/test_api.py that calls the new endpoint with the Flask test client on a happy path and asserts the correct status code (201 for POST, 200 for GET/PATCH, 204 for DELETE).
- Add one test that sends bad input and asserts 422.
- Run pytest -q; all tests must pass. Run ruff check ..
- Report: files changed, the route path and method added, and the pytest output.

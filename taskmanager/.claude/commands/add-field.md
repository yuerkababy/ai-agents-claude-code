# Use to add one new field to tasks end to end (seed data, create, update, responses, tests). Do not use for a new resource (use /scaffold-endpoint) or to change or remove an existing field.

## Goal
Add the task field described in $ARGUMENTS everywhere a task is created,
updated, or returned. $ARGUMENTS gives the field name, its type, its allowed
values, and its default (example: `estimate int 1-8 default 1`). If any of
those four parts is missing or unclear, stop and ask instead of guessing.
 
Add the word `filter` to $ARGUMENTS to also support GET /api/tasks?<field>=value.

## Context
- Use `priority` as the canonical example for every layer:
  - Seed data: the TASKS dict in services/tasks.py. Give seed tasks DIFFERENT
values so a filter test can show something being excluded.
  - Validation: the private `_validate_priority` helper in services/tasks.py.
  - Service functions: create_task, update_task, and list_tasks (filter).
  - Routes: create_task_route, update_task_route, and the GET tasks route in
 routes/api.py.
  - Tests: the priority HTTP tests in tests/test_api.py.
- Errors: bad values raise ValidationError("<field>", "<message>") from
utils/errors.py, which the API turns into a 422.

## Constraints
- One validator: write a single private `_validate_<field>` helper and call it
  from create_task, update_task, and (if filtering) list_tasks. Do not copy the
  validation into each function.
- Bad input is always a 422, never silently ignored. For a filter, pass the raw query string from the route and convert/validate it in the service. Do not use `request.args.get(..., type=int)`, which turns bad input into None.
- Signatures: the only allowed change is appending ONE optional keyword
  parameter with a default to create_task and update_task, so existing callers in routes/api.py and tests still work. Do not rename, reorder, or remove any parameter or function.
- Routes stay thin: read the request, call one service function, return jsonify(...). No validation in routes.
- Touch only services/tasks.py, routes/api.py, and tests/test_api.py. Do notmodify process_order, services/users.py, utils/errors.py, or existing tests in tests/test_tasks.py.
- New tests create their own tasks first and never assert counts in TASKS.
- Do not write memory notes or any file not listed above.

## Verification
- Run `pytest -q` after each layer (seeds + create, then update, then filter). Do not start the next layer until all tests pass.
- Tests must cover: the default value when the field is omitted on POST; a valid value on POST and on PATCH; an invalid value on POST and on PATCH returning 422; the field appearing in task responses; and, if filtering, one included task, one excluded task, and a bad filter value returning 422.
- Finish with `ruff check .` and report the files changed, the tests added, and the final pytest output.

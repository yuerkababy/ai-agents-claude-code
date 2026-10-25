# DECOMPOSITION

**Feature:** Users can pick how they want to be notified: `email`, `sms`, or `none`. If they haven't picked, it's `none` by default.
 
**Decision I made before starting:** The setting is saved on each user as `notification_pref`. If the user picks "none" (or hasn't picked anything), it's saved as empty (`None`), which shows up as `null` in the API. Any other value is rejected with a `ValidationError`.
 
**How I ran each subagent:** I closed and reopened Claude Code before each one so it started fresh, pasted the prompt exactly as written below, and ran `pytest -q` before moving on to the next one.

---

| Field | Value |
|---|---|
| **Subagent #** | SA-1: Service / Data Layer
| **Input** | `CLAUDE.md`, `services/users.py`, `utils/errors.py` |
| **Task** | Add the notification setting to users, plus functions to list users and to read and change the setting. |
| **Output** | `services/users.py` (edited) |
| **Constraint** | Do not touch `routes/api.py`, `services/tasks.py`, `utils/errors.py`, or anything in `tests/`. Do not change how `get_user` or `create_user` are called. |
| **Hand-off** | The names of the new functions SA-2 will use: `list_users()`, `get_notification_pref(user_id)`, `set_notification_pref(user_id, pref)`. "none" is saved as `None`. |

**Prompt (paste exactly):**
```
Goal: Add a notification preference to users in services/users.py.
- Add "notification_pref": None to every seed record in USERS and to the record built in create_user.
- Add module constant NOTIFICATION_PREFS = ("email", "sms", "none").
- Add list_users() -> list[dict] returning all users.
- Add get_notification_pref(user_id: int) -> str | None. Unknown user → NotFoundError("User").
- Add set_notification_pref(user_id: int, pref: str) -> dict. Unknown user → NotFoundError("User").
  pref not in NOTIFICATION_PREFS → ValidationError("notification_pref", "must be one of: email, sms, none").
  Store "none" as None. Validate before mutation. Return the updated user dict.
Follow the get_user / create_user pattern exactly (type hints, Google docstrings).
Constraints: Only edit services/users.py. Do not touch routes/api.py, services/tasks.py,
utils/errors.py, or tests/. Do not change get_user or create_user signatures.
Verification: pytest -q and ruff check . must pass.
```

**pytest -q result:**
```
26 passed in 0.27s
```
**Fixes made in this session (if any):**
None. Claude only edited services/users.py. It pointed out that the new functions don't have tests yet, which is expected because SA-3 writes them.
---

## SA-2: API / routes layer

| Field | Value |
|---|---|
| **Subagent #** | SA-2: API / Routes Layer
| **Input** | `CLAUDE.md`, `routes/api.py`, `services/users.py` (read only) |
| **Task** | Add the web addresses (endpoints) so the app can list users and read or change a user's notification setting. |
| **Output** | `routes/api.py` (edited) |
| **Constraint** | Do not touch `services/users.py`, `services/tasks.py`, `utils/errors.py`, or anything in `tests/`. Each route only calls one function from `services/`, with no extra logic. |
| **Hand-off** | The three new endpoints SA-3 will test: `GET /api/users`, `GET /api/users/<id>/notifications`, `PATCH /api/users/<id>/notifications`, and what each should return: 200 OK, 404 not found, or 422 bad value. |

**Prompt (paste exactly):**
```
Goal: Add notification-preference routes to routes/api.py using the existing service functions
in services/users.py (list_users, get_notification_pref, set_notification_pref). Read them; do not edit them.
- GET /users → jsonify(list_users())
- GET /users/<int:user_id>/notifications → jsonify({"notification_pref": get_notification_pref(user_id)})
- PATCH /users/<int:user_id>/notifications with JSON body {"notification_pref": "<value>"}
  → jsonify(set_notification_pref(user_id, value)). A missing key in the body must produce a 422,
  not a 500 KeyError.
Each route calls exactly one service function. Errors are handled by the existing @api.errorhandler(AppError).
Constraints: Only edit routes/api.py. Do not touch services/, utils/, or tests/.
Verification: pytest -q and ruff check . must pass.
```

**pytest -q result:**
```
26 passed in 0.25s
```
**Fixes made in this session (if any):**
None. Claude only edited `routes/api.py`. To handle a request with no `notification_pref` value, it used `data.get(...)` in the route. That passes an empty value to SA-1's function, which already rejects it, so `services/users.py` didn't need to change.
---

## SA-3: Tests

| Field | Value |
|---|---|
| **Subagent #** | SA-3: Tests
| **Input** | `CLAUDE.md`, `services/users.py`, `routes/api.py`, `tests/test_tasks.py` (only as an example of test style) |
| **Task** | Write tests that check the notification setting works, both the functions and the web addresses. |
| **Output** | `tests/test_users.py` (new file) |
| **Constraint** | Do not touch `services/users.py`, `services/tasks.py`, `routes/api.py`, `utils/errors.py`, or `tests/test_tasks.py`. If a test fails, report it instead of changing the code to make it pass. |
| **Hand-off** | All tests passing (`pytest -q`), which shows the whole feature works. |

**Prompt (paste exactly):**
```
Goal: Create tests/test_users.py covering the notification preference feature.
- Service tests: default is None; set_notification_pref works for "email", "sms", and "none"
  ("none" reads back as None); invalid value raises ValidationError; unknown user raises NotFoundError
  for both get_notification_pref and set_notification_pref.
- HTTP tests using app.test_client() from app.py: GET /api/users includes notification_pref on each user;
  GET /api/users/1 includes notification_pref; PATCH /api/users/<id>/notifications returns 200 for a
  valid value, 422 for an invalid value, 422 for a missing key, 404 for an unknown user.
Follow CLAUDE.md: assert specific exception classes; no count assertions; USERS is shared across tests,
so create a user inside a test when you need a clean starting value.
Constraints: Only create tests/test_users.py. Do not touch services/, routes/, utils/, or tests/test_tasks.py.
If a test fails because of a source bug, stop and report it instead of editing source.
Verification: pytest -q and ruff check . must pass.
```

**pytest -q result:**
```
39 passed in 0.33s
```
**Fixes made in this session (if any):**
None. Claude only created `tests/test_users.py`. No test failed, so it never needed to change any code.
---

## Divergence

**1. Did Claude follow the constraint field for every subagent?**
Yes, all three stayed inside their file boundary. SA-1 edited only services/users.py, SA-2 edited only routes/api.py and SA-3 created only tests/test_users.py. The closest call was SA-2. Its prompt said that a request missing the notification_pref value should return an error, 422. The easiest way to do that would have been to add a check in services/users.py, but SA-2 wasn't allowed to touch that file. Instead, Claude handled it in routes/api.py and relied on the check SA-1 had already written, which rejects any value that isn't email, sms, or none. 

**2. Did any subagent's output break the next subagent's assumption?**
Nothing broke because pytest had all passing tests, but SA-2 depended on something I never wrote down in SA-1's Hand-off, that set_notification_pref rejects an empty value. It only worked because of how SA-1 happened to write its check. SA-2 also found two cases none of my hand-offs mentioned, where an unknown user with a missing value gets a "not found" error (404) instead of an "invalid" error (422), and a request that isn't JSON gets a different error (415). SA-3 didn't write tests for either case. I didn't need to fix anything, but the pipeline worked partly by luck. 

**3. Would you write the decomposition differently a second time?**
Yes, I would change three things. First, I would write in SA-1's Hand-off that set_notification_pref rejects an empty value, since SA-2 depended on it. Second, I would add the 404 and 415 cases to SA-2's Hand-off so that SA-3 would know to test them. Third, I would add a step before each subagent to check that Claude's memory folder is empty, because closing and reopening Claude Code. 



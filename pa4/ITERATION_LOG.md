## Session 1: 10/04/26

### Prompt used
> Add error handling to the get_task function in @services/tasks.py. Do not change the function signature. Run pytest -v when done.

### What Claude did
- **services/tasks.py:** Claude imported NotFoundError and updated get_task so it checks if task_id not in TASKS first. If the ID doesn't exist, it raises NotFoundError("Task"), the same way get_user does. It also added a Google-style docstring like the one in get_user, and it didn't change the function signature.
- **tests/test_tasks.py:** Claude added a new test, test_get_task_missing_raises_not_found, that checks for NotFoundError specifically. It also pointed out something I hadn't noticed. The existing test_get_task_invalid only checks for any Exception, so it would have passed even before the fix. It didn't touch the four existing tests.
- **Reported but not changed:** Claude noticed that process_order has the same KeyError bug, and that create_task has no docstring and accepts an empty title. It told me about both but left them alone.
- **What went wrong:** ruff check . found one error, an F401 in routes/api.py line 2 (process_order is imported but never used). Claude didn't fix it, but it suggested either removing the import or running ruff check --fix. It also said that since CLAUDE.md mentions routes/api.py importing process_order, "a route that uses it may be missing," and asked me to decide.
- **pytest -v result:** 5 passed, 0 failed
- **Corrections needed:** 1 (an extra question about a lint error that had nothing to do with the task)

### Observation
Claude followed most of my CLAUDE.md, but two gaps led to an extra question:

- **Conventions rules:** Claude used an AppError subclass instead of a raw exception, checked that the task exists before reading it like get_user does, added a Google-style docstring, and made the new test check for NotFoundError specifically.
- **Do not touch rules:** It only changed get_task and left the existing tests alone.
- **Scope rule:** It reported the process_order bug instead of fixing it.
- **Commands rule:** It ran ruff check . like I told it to, but that turned up the F401 error in routes/api.py, and it stopped to ask about it. My CLAUDE.md never said that error was already there and expected.
- **Misleading wording:** The Do not touch line about process_order ended with "routes/api.py and the tests import it." Claude took that to mean the import was there on purpose, and guessed that a route using it might be missing.

### CLAUDE.md update
Changed in **Commands**:

> Lint: ruff check . The only expected error is F401 in routes/api.py line 2: process_order is imported but no route uses it. This is known and intentional; no route is missing. Don't fix it, don't run ruff check --fix, and don't mention it in your summary. Fix any other lint error in files you changed.

I changed this line because in Session 1 Claude ran ruff check ., found the old F401 in routes/api.py, read the "routes/api.py and the tests import it" wording as a sign that a route was missing, and asked me what to do, even though none of it had anything to do with get_task.

---

## Session 2: 10/04/26

### Prompt used
> Refactor create_task in @services/tasks.py to match the style of get_user in @services/users.py exactly. Run pytest -v when done.

### What Claude did
- **services/tasks.py:** Claude gave create_task a Google-style docstring with Args, Returns, and Raises. Now a blank or whitespace-only title raises ValidationError("title", "cannot be empty") before anything gets saved to TASKS. Before this, it would just save an empty task. Claude added ValidationError to the import, kept the same function name and arguments, and moved the dict onto one line.
- **tests/test_tasks.py:** Claude added two new tests. test_create_task_valid creates a task and then looks it up by the ID it got back, instead of counting tasks. test_create_task_empty_title_raises_validation_error checks that a blank title raises ValidationError. It didn't touch the existing tests.
- **Reported but not changed:** process_order still has the KeyError bug. Claude left it alone because my CLAUDE.md says to only change the function named in the prompt.
- **What went wrong:** create_task still doesn't check whether user_id belongs to a real user. Claude stopped and asked me whether services/tasks.py is allowed to import from services/users.py, so the task was only partly done.
- **pytest -v result:** 7 passed, 0 failed (the 5 from before plus 2 new ones)
- **Corrections needed:** 1 (a decision I had to make about checking user_id)

### Observation
Most of my CLAUDE.md worked this time. The prompt only mentioned get_user, but Claude also copied create_user's validation pattern, because my CLAUDE.md lists both functions as the example to follow and says to validate before changing any data. The shared-state rule worked too, since test_create_task_valid looks the task up by its ID instead of counting user 1's tasks. The scope rule held again for process_order. My Session 1 update also worked: Claude said its files were lint-clean and didn't bring up the F401 in routes/api.py at all.

My honest failure is that CLAUDE.md didn't stop create_task from accepting a user_id for a user who doesn't exist. Nothing in the file said whether one service could use another, so Claude couldn't decide on its own and left the check out. The rule was missing.

### CLAUDE.md update
Added in **Architecture**:

> services/tasks.py may import get_user from services/users.py to check that a user exists. An unknown user_id raises NotFoundError("User"). services/users.py must never import from services/tasks.py.

I added this because in Session 2 Claude left create_task accepting any user_id and stopped to ask whether services/tasks.py could import from services/users.py, which my CLAUDE.md didn't cover.

---

## Session 3: 10/04/26

### Prompt used
> Add a new function to @services/tasks.py that returns all tasks for a given user_id. Follow the same pattern as the existing functions. Add a test for it. Run pytest -v when done.

### What Claude did
- **services/tasks.py:** Claude added get_tasks_for_user(user_id) with type hints, a Google-style docstring, and validation before reading any data. It calls get_user(user_id) first, so an unknown user raises NotFoundError("User"). It imported get_user from services/users.py, and nothing imports in the other direction. If a user exists but has no tasks, they just get an empty list.
- **tests/test_tasks.py:** Claude added two tests. test_get_tasks_for_user_valid creates a task for user 2 inside the test, then checks that the result includes that task and task 3 but not task 1. It checks specific task IDs instead of counting. test_get_tasks_for_user_unknown_user_raises_not_found checks that user 999 raises NotFoundError. It didn't touch the existing tests.
- **Reported but not changed:** the process_order KeyError bug, and the missing user check in create_task.
- **pytest -v result:** 9 passed, 0 failed
- **ruff check .:** no new lint errors, and it didn't mention the known F401
- **Corrections needed:** 0

### Observation
This was the cleanest session. Claude followed every rule that applied, and I didn't have to step in once:

- **Session 2 update:** Claude imported get_user from services/users.py to check that the user exists, raised NotFoundError("User") for an unknown user, and only imported in one direction. The question that stopped it in Session 2 didn't come up.
- **Shared-state rule:** The test creates its own task and checks specific IDs instead of counting, and Claude said it did this because TASKS is shared between tests.
- **Architecture rule:** Claude didn't create a repositories/ folder. It used the TASKS dict directly, like my CLAUDE.md describes.
- **Session 1 update:** Running ruff check . didn't lead to another question about the F401 in routes/api.py.
- **Scope rule:** It reported process_order and create_task instead of changing them.

### CLAUDE.md update
None. Nothing was missed or misunderstood this time, so there wasn't anything new to fix. The create_task user check that Claude mentioned is the same gap from Session 2. It's not a new mistake, and fixing it would be its own task.

---

**Honest failure:** In Session 2, my CLAUDE.md didn't stop create_task from accepting a user_id for a user who doesn't exist. Nothing said whether one service could import from another, so Claude couldn't decide and left the check out. That gap is still in the code, and Claude pointed it out again in Session 3.

**Evidence of improvement:** Sessions 1 and 2 each needed one correction, and both times it was an extra question caused by a rule that was missing or confusing. Session 3 needed none. Both updates kept the same problem from happening again. The F401 note stopped the lint question from Session 1, and the get_user rule let Claude handle an unknown user in Session 3 without asking, which is exactly where it got stuck in Session 2.

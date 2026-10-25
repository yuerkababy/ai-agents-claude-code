#!/usr/bin/env bash
# add_docstrings.sh - add or improve PEP 257 docstrings in a Python file using `claude -p`.
#
# Usage: ./add_docstrings.sh path/to/file.py
#
# Safety:
#   - the original file is backed up first (FILE.YYYYmmddHHMMSS.bak)
#   - Claude's output is checked before it replaces anything: it must parse,
#     and its AST must be identical to the original's once docstrings are
#     ignored (so no logic can have changed)
#   - on any failure the original file is left untouched

set -euo pipefail

usage() {
    echo "Usage: $(basename "$0") <python-file.py>" >&2
    echo "Adds or improves PEP 257 docstrings on every function/method in the file." >&2
}

die() {
    echo "Error: $*" >&2
    exit 1
}

# --- Validate arguments ------------------------------------------------------
if [ "$#" -ne 1 ]; then
    usage
    exit 2
fi

file="$1"

[ -e "$file" ] || die "file not found: $file"
[ -f "$file" ] || die "not a regular file: $file"
[ -r "$file" ] || die "file is not readable: $file"
[ -w "$file" ] || die "file is not writable: $file"
[ -s "$file" ] || die "file is empty: $file"
case "$file" in
    *.py) ;;
    *) die "expected a Python file ending in .py, got: $file" ;;
esac

command -v claude >/dev/null 2>&1 || die "'claude' CLI not found on PATH"

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    die "python3 (or python) is required to verify the result"
fi

"$PY" -m py_compile "$file" 2>/dev/null || die "the input file does not compile; fix its syntax first: $file"

# --- Back up the original ----------------------------------------------------
backup="${file}.$(date +%Y%m%d%H%M%S).bak"
cp -p -- "$file" "$backup" || die "could not create backup: $backup"
echo "Backup created: $backup"

tmp_out="$(mktemp)"
tmp_verify="$(mktemp)"
trap 'rm -f "$tmp_out" "$tmp_verify"' EXIT

# --- Ask Claude for the documented file ---------------------------------------
read -r -d '' prompt <<'EOF' || true
You will receive a Python source file on stdin. Return the COMPLETE file with
docstrings added or improved on every function, method, and async function.

Rules:
- Follow PEP 257: triple double quotes, a one-line summary in the imperative
  mood ending with a period, then a blank line and more detail only when it
  helps (arguments, return value, raised exceptions).
- If a function already has a docstring, improve it only if it is missing,
  wrong, or unclear; otherwise keep it.
- Do NOT change any code: no renaming, reformatting, reordering, import
  changes, type-hint changes, or logic changes. Do not touch comments.
- Do not add docstrings to anything that is not a function or method, but keep
  any existing module or class docstrings exactly as they are.
- Output ONLY the raw contents of the Python file. No markdown fences, no
  explanations, no preamble.
EOF

echo "Asking Claude to add docstrings (this can take a minute)..."
if ! claude -p "$prompt" < "$file" > "$tmp_out"; then
    die "claude -p failed; original file unchanged (backup: $backup)"
fi

# Strip a markdown code fence if the model added one despite instructions.
if head -n 1 "$tmp_out" | grep -q '^```'; then
    sed -e '1d' -e '${/^```[[:space:]]*$/d;}' "$tmp_out" > "$tmp_verify"
    mv "$tmp_verify" "$tmp_out"
    tmp_verify="$(mktemp)"
fi

[ -s "$tmp_out" ] || die "claude returned no output; original file unchanged (backup: $backup)"

# --- Verify: parses, and only docstrings differ -------------------------------
if ! "$PY" - "$file" "$tmp_out" <<'PYEOF'
import ast
import sys

original_path, new_path = sys.argv[1], sys.argv[2]


def load(path):
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=path)


def strip_docstrings(tree):
    """Remove leading docstring statements; keep everything else intact."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:]
    return tree


try:
    new_tree = load(new_path)
except SyntaxError as exc:
    sys.exit(f"the generated file does not parse: {exc}")

missing = [
    f"{n.name} (line {n.lineno})"
    for n in ast.walk(new_tree)
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and ast.get_docstring(n) is None
]

# strip_docstrings mutates the trees, so the missing-docstring scan above must run first.
original_tree = load(original_path)
if ast.dump(strip_docstrings(original_tree)) != ast.dump(strip_docstrings(new_tree)):
    sys.exit("the generated file changes code beyond docstrings")

if missing:
    print("Warning: functions still without a docstring: " + ", ".join(missing), file=sys.stderr)
PYEOF
then
    die "verification failed; original file unchanged (backup: $backup)"
fi

# --- Apply ----------------------------------------------------------------------
cat "$tmp_out" > "$file"
echo "Done: docstrings updated in $file"
echo "Restore the original with: cp -- \"$backup\" \"$file\""

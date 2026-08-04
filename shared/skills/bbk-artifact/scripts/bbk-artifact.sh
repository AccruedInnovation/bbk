#!/bin/sh
set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${BBK_PYTHON:-}" ]; then
	exec "$BBK_PYTHON" -B -X utf8 "$SCRIPT_DIR/bbk_artifact.py" "$@"
elif command -v python3 >/dev/null 2>&1; then
	exec python3 -B -X utf8 "$SCRIPT_DIR/bbk_artifact.py" "$@"
elif command -v python >/dev/null 2>&1; then
	exec python -B -X utf8 "$SCRIPT_DIR/bbk_artifact.py" "$@"
else
	printf '%s\n' '{"schema":"bbk.artifact-skill-binding.v1","status":"BLOCKED","code":"PYTHON_NOT_RESOLVED","message":"No Python interpreter was found for the BBK artifact skill wrapper.","smallest_next_action":"Set BBK_PYTHON to the Python executable recorded by the BBK installation."}' >&2
	exit 127
fi

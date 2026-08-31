#!/usr/bin/env bash
# Execute the capstone notebook with the workspace virtual environment.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/run_notebook.sh /absolute/path/to/Galleria_Capstone" >&2
  exit 2
fi

project_dir="$1"
workspace_dir="$(cd "$(dirname "$0")/.." && pwd)"
venv_python="$workspace_dir/.venv/bin/python"
notebook="$workspace_dir/notebooks/Galleria_Intelligence_Clean_Capstone_Colab.ipynb"

if [[ ! -x "$venv_python" ]]; then
  echo "Missing .venv. Run the setup commands in README.md first." >&2
  exit 1
fi
if [[ ! -d "$project_dir" ]]; then
  echo "Project directory does not exist: $project_dir" >&2
  exit 1
fi

"$venv_python" -m ipykernel install --prefix "$workspace_dir/.venv" \
  --name galleria-intelligence --display-name "Galleria Intelligence"

GALLERIA_PROJECT_DIR="$project_dir" "$venv_python" -m jupyter nbconvert \
  --to notebook --execute "$notebook" \
  --output Galleria_Intelligence_Executed.ipynb \
  --output-dir "$project_dir/outputs" \
  --ExecutePreprocessor.timeout=600 \
  --ExecutePreprocessor.kernel_name=galleria-intelligence

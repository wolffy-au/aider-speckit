#!/bin/sh

set -e

# git rebase develop

pyenv local 3.12.10

if [ -d ../.venvs/uplift-linter/ ]; then
    echo "Virtual environment already exists, skipping creation"
else
    python -m venv ../.venvs/uplift-linter
fi
source ../.venvs/uplift-linter/Scripts/activate

../refresh-env.sh
python -m pip install --upgrade -e ../aider-speckit

export OLLAMA_API_BASE="http://10.61.1.110:11434"

cat > .aider.conf.yml << 'EOF'
auto-accept-architect: true
auto-commits: true
auto-lint: true
auto-test: true
chat-mode: architect
gitignore: false
lint-cmd:
  - "python: flake8"
map-refresh: always
test-cmd: "pytest"
watch-files: true
# model: ollama_chat/qwen3-coder
model: gpt-5.1-codex-mini
weak-model: gpt-5-nano
EOF

cat > .aider.model.settings.yml << 'EOF'
- name: ollama_chat/qwen3-coder
  extra_params:
    num_ctx: 262000
EOF


python -m pip install pyright typing-extensions types-requests types-pyyaml

set +e

find tests/ -name "*.py" -not -path "*/.*" -not -path "*/__pycache__*" | while read -r file; do
    printf "Checking %s...\n" "$file"
    errors=$(pyright "$file" 2>&1)
 
    while [ $? -ne 0 ]; do
        printf "Found issues in %s. Sending to Aider...\n" "$file"
        aider "$file" -m "Fix these pyright errors: $errors" --yes-always --git-commit-verify --attribute-co-authored-by
        # printf "Checking %s...\n" "$file"
        # errors=$(pyright "$file" 2>&1)
	sleep 1
    done
    printf "%s is clean.\n" "$file"
done
pyright tests/

#!/bin/bash

# Exit immediately on error, treat unset variables as an error, and fail if any command in a pipeline fails.
set -euo pipefail

# Function to run a command and show logs only on error
run_command() {
    local command_to_run="$*"
    local output
    local exit_code
    
    # Capture all output (stdout and stderr)
    output=$(eval "$command_to_run" 2>&1) || exit_code=$?
    exit_code=${exit_code:-0}
    
    if [ $exit_code -ne 0 ]; then
        echo -e "\033[0;31m[ERROR] Command failed (Exit Code $exit_code): $command_to_run\033[0m" >&2
        echo -e "\033[0;31m$output\033[0m" >&2
        
        exit $exit_code
    fi
}

# Installing UV (Python package manager)
echo -e "\n🐍 Installing UV - Python Package Manager..."
run_command "pipx install uv"
echo "✅ Done"

# Install Requirements
# echo -e "\n📦 Installing project dependencies..."
# run_command "uv pip sync requirements.txt \`find requirements -iname requirements-*.txt\` --system"


# Installing CLI-based AI Agents

echo -e "\n🤖 Installing Aider CLI..."
run_command "uv tool install aider-chat --from git+https://github.com/wolffy-au/aider-speckit.git"
echo "✅ Done"

# echo -e "\n🤖 Installing Specify CLI..."
# run_command "uv tool install specify-cli --from git+https://github.com/wolffy-au/spec-kit-aider.git@feat-speckit-aider"
# echo "✅ Done"

echo -e "\n🧹 Cleaning cache..."
run_command "sudo apt-get autoclean"
run_command "sudo apt-get clean"

echo "✅ Setup completed. Happy coding! 🚀"

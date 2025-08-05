#!/usr/bin/env bash
# shellcheck disable=SC2174
#
# Initialize artifacts volume with proper permissions
# This script ensures all agent containers can read/write to the artifacts volume
#
# Exit on error, undefined variables, and pipe failures
set -euo pipefail

# Constants
readonly ARTIFACTS_DIR="/artifacts"
readonly AGENT_UID=1001
readonly AGENT_GID=1001

echo "Initializing artifacts volume permissions..."

# Create base directory structure with proper permissions in one step
# -m 775 sets permissions during creation
# -p creates parent directories as needed
if ! mkdir -p -m 775 "${ARTIFACTS_DIR}"; then
    echo "ERROR: Failed to create artifacts directory" >&2
    exit 1
fi

# Set ownership to the standard agent user (1001)
# This matches the user ID used in agent containers
if ! chown -R "${AGENT_UID}:${AGENT_GID}" "${ARTIFACTS_DIR}"; then
    echo "ERROR: Failed to set ownership on artifacts directory" >&2
    exit 1
fi

# Set permissions to allow read/write/execute for user and group
# 775 allows group members to also write, which helps with permission issues
if ! chmod -R 775 "${ARTIFACTS_DIR}"; then
    echo "ERROR: Failed to set permissions on artifacts directory" >&2
    exit 1
fi

# Set sticky bit on directory to preserve ownership for new files
# This ensures that files created by different users maintain proper group ownership
if ! chmod +t "${ARTIFACTS_DIR}"; then
    echo "ERROR: Failed to set sticky bit on artifacts directory" >&2
    exit 1
fi

echo "Artifacts volume initialized successfully"

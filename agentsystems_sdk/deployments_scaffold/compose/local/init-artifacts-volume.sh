#!/bin/bash
# Initialize artifacts volume with proper permissions
# This script ensures all agent containers can read/write to the artifacts volume

echo "Initializing artifacts volume permissions..."

# Create base directory structure
mkdir -p /artifacts

# Set ownership to the standard agent user (1001)
# This matches the user ID used in agent containers
chown -R 1001:1001 /artifacts

# Set permissions to allow read/write/execute for user and group
# 775 allows group members to also write, which helps with permission issues
chmod -R 775 /artifacts

# Set sticky bit on directory to preserve ownership for new files
chmod +t /artifacts

echo "Artifacts volume initialized successfully"

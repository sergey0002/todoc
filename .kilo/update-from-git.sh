#!/bin/bash
set -e

echo "=== Fetching from origin ==="
git fetch origin

echo "=== Resetting main repo to origin/master ==="
git reset --hard origin/master

echo "=== Resetting submodules ==="
git submodule update --init --recursive --force

echo "=== Done ==="
git status
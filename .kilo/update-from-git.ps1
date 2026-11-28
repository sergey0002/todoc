# Update from Git - PowerShell version
Write-Host "=== Fetching from origin ===" -ForegroundColor Cyan
git fetch origin

Write-Host "=== Resetting main repo to origin/master ===" -ForegroundColor Cyan
git reset --hard origin/master

Write-Host "=== Resetting submodules ===" -ForegroundColor Cyan
git submodule update --init --recursive --force

Write-Host "=== Done ===" -ForegroundColor Green
git status
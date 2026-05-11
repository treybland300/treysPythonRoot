param(
    [string]$Message = "Update app",
    [string]$Branch = "main"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path .git)) {
    Write-Error "This script must be run from the repository root where .git is present."
    exit 1
}

Write-Host "Repository root: $scriptDir"
Write-Host "Branch: $Branch"

$gitStatus = git status --short
if (-not $gitStatus) {
    Write-Host "No local changes detected."
    Write-Host "Pulling latest remote changes from origin/$Branch..."
    git pull origin $Branch
    exit 0
}

Write-Host "Staging all changes..."
git add .

Write-Host "Committing with message: $Message"
$commitResult = git commit -m "$Message"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Commit failed. Please review the git output above."
    exit $LASTEXITCODE
}

Write-Host "Pushing to origin/$Branch..."
git push origin $Branch
if ($LASTEXITCODE -ne 0) {
    Write-Error "Push failed. Check your network/authentication and try again."
    exit $LASTEXITCODE
}

Write-Host "Push complete."

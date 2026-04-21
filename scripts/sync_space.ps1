param(
    [string]$RepoId = "PingKuei/Qwen3-TTS",
    [string]$LocalDir = ".\\upstream\\Qwen3-TTS"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command hf -ErrorAction SilentlyContinue)) {
    throw "hf CLI not found in PATH."
}

Write-Host "Checking Hugging Face authentication..."
hf auth whoami | Out-Null

Write-Host "Syncing Space $RepoId into $LocalDir"
hf download $RepoId --repo-type space --local-dir $LocalDir

Write-Host "Done."

<# 
FunSearch Quick Start Script
Usage:
  .\run.ps1                     # Run with default config
  .\run.ps1 -Dataset orlib      # Use OR-Library dataset
  .\run.ps1 -Size large         # Use large instances
  .\run.ps1 -Generations 100    # Run 100 generations
  .\run.ps1 -Help               # Show help
#>

param(
    [string]$Dataset = "random",
    [string]$Size = "small",
    [int]$Generations = 50,
    [int]$Population = 15,
    [int]$Islands = 3,
    [string]$RunId = "",
    [string]$ApiKey = "",
    [switch]$Demo,
    [switch]$Yes,
    [switch]$Help
)

# Load .env file
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            if (-not [Environment]::GetEnvironmentVariable($key)) {
                [Environment]::SetEnvironmentVariable($key, $value)
            }
        }
    }
}

if ($Help) {
    Write-Host @"
================================================================
              FunSearch Quick Start Script
================================================================

Parameters:
  -Dataset     Dataset type: random or orlib (OR-Library)
  -Size        Instance size: small or large
  -Generations Max generations (default: 50)
  -Population  Candidates per generation (default: 15)
  -Islands     Number of islands (default: 3)
  -RunId       Run identifier (default: auto-generated)
  -ApiKey      DeepSeek API Key (or use DEEPSEEK_API_KEY env var)
  -Demo        Use FakeProvider demo mode (no API Key needed)
  -Yes         Skip confirmation
  -Help        Show this help

Examples:
  .\run.ps1                              # Default config
  .\run.ps1 -Demo                        # Demo mode (no API)
  .\run.ps1 -Dataset orlib -Size large   # OR-Library large dataset
  .\run.ps1 -Generations 100 -Population 30
  .\run.ps1 -ApiKey "sk-xxx"             # Specify API Key

Estimated Time (50 generations):
  - random/small: ~3-4 hours
  - random/large: ~5-6 hours
  - orlib/small:  ~4-5 hours
  - orlib/large:  ~6-8 hours
"@
    exit 0
}

# Banner
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "      FunSearch - LLM-Guided Evolutionary Search" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# Check API Key
if (-not $Demo) {
    if ($ApiKey) {
        $env:DEEPSEEK_API_KEY = $ApiKey
    }
    
    if (-not $env:DEEPSEEK_API_KEY) {
        Write-Host "Error: DEEPSEEK_API_KEY not set" -ForegroundColor Red
        Write-Host "   Options:" -ForegroundColor Yellow
        Write-Host "   1. .\run.ps1 -ApiKey 'sk-xxx'" -ForegroundColor Yellow
        Write-Host "   2. Create .env file with DEEPSEEK_API_KEY=sk-xxx" -ForegroundColor Yellow
        Write-Host "   3. .\run.ps1 -Demo  (demo mode)" -ForegroundColor Yellow
        exit 1
    }
}

# Generate Run ID
if (-not $RunId) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $RunId = "funsearch_${Dataset}_${Size}_${timestamp}"
}

# Display config
Write-Host "Config:" -ForegroundColor Green
Write-Host "   Run ID:      $RunId"
Write-Host "   Dataset:     $Dataset ($Size)"
Write-Host "   Generations: $Generations"
Write-Host "   Population:  $Population"
Write-Host "   Islands:     $Islands"
if ($Demo) {
    Write-Host "   Mode:        Demo (FakeProvider)" -ForegroundColor Yellow
} else {
    Write-Host "   Mode:        DeepSeek API" -ForegroundColor Green
}
Write-Host ""

# Estimate time
$totalCandidates = $Generations * $Islands * $Population
$avgTimePerCandidate = if ($Demo) { 0.1 } else { 11 }
$estimatedSeconds = $totalCandidates * $avgTimePerCandidate
$estimatedTime = [TimeSpan]::FromSeconds($estimatedSeconds)
Write-Host "Estimated time: $($estimatedTime.Hours)h $($estimatedTime.Minutes)m (~$totalCandidates candidates)" -ForegroundColor Cyan
Write-Host ""

# Confirm
if (-not $Yes) {
    $confirm = Read-Host "Press Enter to start, or 'q' to cancel"
    if ($confirm -eq 'q') {
        Write-Host "Cancelled" -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "Starting experiment..." -ForegroundColor Green
Write-Host ""

# Run using Python script
python run.py --dataset $Dataset --size $Size --generations $Generations --population $Population --islands $Islands --run-id $RunId --yes $(if ($Demo) { "--demo" } else { "" })

Write-Host ""
Write-Host "Done! Results saved in: artifacts/$RunId/" -ForegroundColor Green

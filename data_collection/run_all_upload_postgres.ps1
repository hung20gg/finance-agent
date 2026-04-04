param(
    [switch]$Parallel
)

# Runs all data_collection/*/upload_postgres.py scripts.
# Usage:
#   .\run_all_upload_postgres.ps1            # sequential (default)
#   .\run_all_upload_postgres.ps1 -Parallel  # run all at once

$ErrorActionPreference = "Stop"

$MODE = if ($Parallel) { "parallel" } else { "sequential" }

$ROOT_DIR = $PSScriptRoot
$PYTHON_BIN = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }

$SCRIPTS = @(
    "commodites/upload_postgres.py"
    "financial_statement/upload_postgres.py"
    "macro/upload_postgres.py"
    "stocks/upload_postgres.py"
    "load_postgres_master_data.py"
)

function Run-One {
    param(
        [string]$RelativeScript
    )
    
    $ScriptDir = Split-Path -Path $RelativeScript -Parent
    $ScriptFile = Split-Path -Path $RelativeScript -Leaf
    
    Write-Host "[START] $RelativeScript"
    
    try {
        Push-Location "$ROOT_DIR\$ScriptDir"
        & $PYTHON_BIN $ScriptFile
        if ($LASTEXITCODE -ne 0) {
            throw "Script failed with exit code $LASTEXITCODE"
        }
        Pop-Location
        Write-Host "[DONE ] $RelativeScript"
    }
    catch {
        Pop-Location
        Write-Host "[FAIL ] $RelativeScript"
        throw $_
    }
}

if ($MODE -eq "parallel") {
    $Jobs = @()
    
    foreach ($Script in $SCRIPTS) {
        $Jobs += Start-Job -ScriptBlock {
            param($Script, $RootDir, $PythonBin)
            $ErrorActionPreference = "Stop"
            $ScriptDir = Split-Path -Path $Script -Parent
            $ScriptFile = Split-Path -Path $Script -Leaf
            
            Write-Host "[START] $Script"
            Push-Location "$RootDir\$ScriptDir"
            & $PythonBin $ScriptFile
            Pop-Location
            Write-Host "[DONE ] $Script"
        } -ArgumentList $Script, $ROOT_DIR, $PYTHON_BIN
    }
    
    $FailedJobs = @()
    foreach ($Job in $Jobs) {
        $Result = Receive-Job -Job $Job -Wait
        if ($Job.State -eq "Failed" -or $LASTEXITCODE -ne 0) {
            $FailedJobs += $Job.Name
        }
    }
    
    if ($FailedJobs.Count -gt 0) {
        Write-Host "[FAIL ] Job(s) failed: $($FailedJobs -join ', ')"
        exit 1
    }
}
else {
    foreach ($Script in $SCRIPTS) {
        Run-One $Script
    }
}

Write-Host "All upload_postgres.py scripts completed successfully."

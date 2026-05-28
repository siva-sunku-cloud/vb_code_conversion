# run.ps1 -- Interactive launcher for Java -> Python Migration Orchestrator
# Usage:  .\run.ps1              # fully interactive
#         .\run.ps1 sample_java/ # pre-fill source dir
# Run with: powershell -ExecutionPolicy Bypass -File run.ps1
#       or: pwsh -File run.ps1

param(
    [string]$SourceArg = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$DataFolder = if ($env:DATA_FOLDER) { $env:DATA_FOLDER } else { Join-Path $HOME "data_code_conversion" }
$PsExe      = if ($PSVersionTable.PSEdition -eq "Core") { "pwsh" } else { "powershell" }

# Prefer the vb_migration conda environment; fall back to any working Python
$CondaEnvName = "vb_migration"
$Python = $null

# Try conda to locate the env's Python
if (Get-Command conda -ErrorAction SilentlyContinue) {
    $envInfo = conda env list 2>$null | Where-Object { $_ -match "^\s*$CondaEnvName\s" }
    if ($envInfo) {
        $envPath = ($envInfo -split '\s+' | Where-Object { $_ -match '^[A-Za-z]:\\' -or $_ -match '^/' } | Select-Object -First 1)
        if ($envPath) {
            $candidate = Join-Path $envPath "python.exe"
            if (Test-Path $candidate) {
                try {
                    $null = & $candidate --version 2>&1
                    if ($LASTEXITCODE -eq 0) { $Python = $candidate }
                } catch {}
            }
        }
    }
}

# Fall back to any working Python on PATH
if (-not $Python) {
    foreach ($cmd in @("python", "python3", "py")) {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) {
            try {
                $null = & $cmd --version 2>&1
                if ($LASTEXITCODE -eq 0) { $Python = $cmd; break }
            } catch {}
        }
    }
}

# ---- Helpers -----------------------------------------------------------------
function HR { Write-Host ("-" * 60) }

function Write-Sug {
    param([string]$Menu, [string]$Suggested)
    if ($Menu -eq $Suggested) { Write-Host "  << suggested" -NoNewline -ForegroundColor Green }
    Write-Host ""
}

# ---- Banner ------------------------------------------------------------------
Write-Host ""
Write-Host "+============================================================+" -ForegroundColor White
Write-Host "|  " -NoNewline -ForegroundColor White
Write-Host "Java -> Python Migration Orchestrator" -ForegroundColor Cyan
Write-Host "|  Hub & Spoke - Test-Driven - MCP Infrastructure" -ForegroundColor DarkGray
Write-Host "+============================================================+" -ForegroundColor White
Write-Host ""

# ==============================================================================
# PHASE 1 -- Environment setup
# ==============================================================================
HR
Write-Host "  PHASE 1 -- Environment Setup" -ForegroundColor White
HR
Write-Host ""
Write-Host "  Has the environment been configured? (Python deps, API keys)"
Write-Host ""
Write-Host "  Y  -- Run setup.ps1       N  -- Already done       Q  -- Quit"
Write-Host ""

$phase1Done = $false
while (-not $phase1Done) {
    $ans = (Read-Host "  Choice [Y/N/Q]").ToUpper().Trim()
    if ($ans -eq "Y") {
        Write-Host ""
        & $PsExe -ExecutionPolicy Bypass -File (Join-Path $ScriptDir "setup.ps1")
        Write-Host ""
        $phase1Done = $true
    } elseif ($ans -eq "N") {
        $phase1Done = $true
    } elseif ($ans -eq "Q") {
        Write-Host ""; Write-Host "  Goodbye."; exit 0
    } else {
        Write-Host "  Please enter Y, N, or Q" -ForegroundColor Yellow
    }
}

# ==============================================================================
# PHASE 2 -- Source directory
# ==============================================================================
Write-Host ""
HR
Write-Host "  PHASE 2 -- Source Code Location" -ForegroundColor White
HR
Write-Host ""

$SourceDir = $null
$Preload   = $SourceArg

while ($null -eq $SourceDir) {
    if ($Preload) {
        $src = $Preload; $Preload = ""
    } else {
        $src = Read-Host "  Source directory [sample_java/]"
        if (-not $src) { $src = "sample_java/" }
    }

    Write-Host ""
    if (Test-Path $src -PathType Container) {
        $jc = (Get-ChildItem -Path $src -Filter "*.java" -Recurse -ErrorAction SilentlyContinue).Count
        Write-Host "  [OK] " -NoNewline -ForegroundColor Green
        Write-Host "$src " -NoNewline -ForegroundColor White
        Write-Host "($jc .java files)" -ForegroundColor DarkGray
    } else {
        Write-Host "  [!]  Directory '$src' not found -- will be resolved at runtime." -ForegroundColor Yellow
    }
    Write-Host ""

    $confirmed = $false
    while (-not $confirmed) {
        $c = (Read-Host "  Continue with '$src'? [Y/N/Q]").ToUpper().Trim()
        if ($c -eq "Y" -or $c -eq "") {
            $SourceDir = $src; $confirmed = $true
        } elseif ($c -eq "N") {
            Write-Host ""; $confirmed = $true   # break inner, re-prompt outer
        } elseif ($c -eq "Q") {
            Write-Host ""; Write-Host "  Goodbye."; exit 0
        } else {
            Write-Host "  Please enter Y, N, or Q" -ForegroundColor Yellow
        }
    }
}

# ==============================================================================
# PHASE 3 -- Pipeline stage selection
# ==============================================================================
$ProjectName = (Split-Path ($SourceDir.TrimEnd('/\')) -Leaf)
$OutputDir   = Join-Path $DataFolder $ProjectName
$StateFile   = Join-Path $OutputDir "migration_state.json"

# Parse state using Python
$StateStatus    = "none"
$StateSuggested = "1"
$StateDisplay   = $null

if ((Test-Path $StateFile) -and $Python) {
    $pyCode = @'
import json, sys

MENU_MAP = {
    "pending":         ("1", "Not yet started"),
    "analyzing":       ("1", "Mid-analysis -- re-run Step 1"),
    "documented":      ("1", "Analysis done, architecture pending"),
    "architected":     ("2", "Step 1 complete -- ready for Step 2"),
    "human_review":    ("2", "Awaiting review -- proceed to Step 2"),
    "tests_generated": ("3", "Step 2 complete -- ready for Step 3"),
    "converting":      ("3", "Mid-conversion -- re-run Step 3"),
    "completed":       ("A", "All steps complete -- restart to redo"),
    "failed":          ("1", "Previous run failed -- restart Step 1"),
}

try:
    with open(sys.argv[1]) as f:
        state = json.load(f)
except Exception as e:
    print("__STATUS__:error")
    print("__NEXT__:1")
    print("  (Could not read state: {})".format(e))
    sys.exit(0)

modules = state.get("modules", {})
if not modules:
    print("__STATUS__:none")
    print("__NEXT__:1")
    print("  (State file has no module data)")
    sys.exit(0)

last_status = "pending"
last_next   = "1"
for mname, m in modules.items():
    status         = m.get("status", "pending")
    next_s, reason = MENU_MAP.get(status, ("1", "Unknown"))
    arts           = ", ".join(m.get("artifacts", {}).keys()) or "none"
    print("  Module : {}".format(mname))
    print("  Status : {}".format(status))
    print("  Note   : {}".format(reason))
    print("  Files  : {}".format(arts))
    print()
    last_status = status
    last_next   = next_s

print("__STATUS__:{}".format(last_status))
print("__NEXT__:{}".format(last_next))
'@

    $tmpScript = Join-Path ([System.IO.Path]::GetTempPath()) "migration_state_parser.py"
    $pyCode | Set-Content -Encoding ASCII $tmpScript
    try {
        $pyOut = & $Python $tmpScript $StateFile 2>$null
    } catch {
        $pyOut = @()
    }
    Remove-Item $tmpScript -ErrorAction SilentlyContinue

    $statusLine = ($pyOut | Where-Object { $_ -match '^__STATUS__:' } | Select-Object -First 1)
    $nextLine   = ($pyOut | Where-Object { $_ -match '^__NEXT__:'   } | Select-Object -First 1)
    $dispLines  = ($pyOut | Where-Object { $_ -notmatch '^__STATUS__:|^__NEXT__:' })

    if ($statusLine) { $StateStatus    = ($statusLine -replace '^__STATUS__:', '').Trim() }
    if ($nextLine)   { $StateSuggested = ($nextLine   -replace '^__NEXT__:',   '').Trim() }
    if ($dispLines)  { $StateDisplay   = $dispLines -join "`n" }
}

# Sub-step default when resuming a partial Step 1
$SubDefault = if ($StateStatus -eq "documented") { "1c" } else { "1a" }

Write-Host ""
HR
Write-Host "  PHASE 3 -- Pipeline Stage" -ForegroundColor White
HR
Write-Host ""
Write-Host "  Project : " -NoNewline; Write-Host $ProjectName -ForegroundColor White
Write-Host "  Output  : " -NoNewline; Write-Host $OutputDir   -ForegroundColor White
Write-Host ""

if ($StateStatus -ne "none" -and $StateDisplay) {
    Write-Host "  Previous run state:" -ForegroundColor Cyan
    Write-Host $StateDisplay
} else {
    Write-Host "  No previous state -- fresh project." -ForegroundColor DarkGray
    Write-Host ""
}

HR
Write-Host ""
Write-Host "  Select a pipeline stage:"
Write-Host ""

Write-Host "  1.  " -NoNewline -ForegroundColor White
Write-Host "Analyze & Design      " -NoNewline
Write-Host "-- understand, document, architect" -NoNewline -ForegroundColor DarkGray
Write-Sug "1" $StateSuggested

Write-Host "  2.  " -NoNewline -ForegroundColor White
Write-Host "Generate Tests        " -NoNewline
Write-Host "-- test-driven development" -NoNewline -ForegroundColor DarkGray
Write-Sug "2" $StateSuggested

Write-Host "  3.  " -NoNewline -ForegroundColor White
Write-Host "Convert & Run         " -NoNewline
Write-Host "-- generate Python code + execute" -NoNewline -ForegroundColor DarkGray
Write-Sug "3" $StateSuggested

Write-Host "  A.  " -NoNewline -ForegroundColor White
Write-Host "Restart All           " -NoNewline
Write-Host "-- wipe state, start from scratch" -ForegroundColor DarkGray

Write-Host "  Q.  " -NoNewline -ForegroundColor White
Write-Host "Quit"
Write-Host ""

$StartStep = "1a"
$menuDone  = $false

while (-not $menuDone) {
    $ch = (Read-Host "  Choice [$StateSuggested]").ToUpper().Trim()
    if (-not $ch) { $ch = $StateSuggested.ToUpper() }

    if ($ch -eq "1") {
        # Offer sub-step menu if Step 1 is partially complete
        if ($StateStatus -eq "documented" -or $StateStatus -eq "analyzing") {
            Write-Host ""
            Write-Host "  Step 1 is partially complete -- where to resume?" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "  1a  " -NoNewline -ForegroundColor White; Write-Host "Re-analyze from scratch"
            Write-Host "  1b  " -NoNewline -ForegroundColor White; Write-Host "Re-run Document agent"
            Write-Host "  1c  " -NoNewline -ForegroundColor White; Write-Host "Re-run Architect agent"
            Write-Host "  Q   " -NoNewline -ForegroundColor White; Write-Host "Quit"
            Write-Host ""

            $ssDone = $false
            while (-not $ssDone) {
                $ss = (Read-Host "  Sub-step [$SubDefault]").ToLower().Trim()
                if (-not $ss) { $ss = $SubDefault.ToLower() }
                if ($ss -eq "1a")   { $StartStep = "1a"; $ssDone = $true }
                elseif ($ss -eq "1b") { $StartStep = "1b"; $ssDone = $true }
                elseif ($ss -eq "1c") { $StartStep = "1c"; $ssDone = $true }
                elseif ($ss -eq "q")  { Write-Host ""; Write-Host "  Goodbye."; exit 0 }
                else { Write-Host "  Enter 1a, 1b, 1c, or Q" -ForegroundColor Yellow }
            }
        } else {
            $StartStep = "1a"
        }
        $menuDone = $true
    } elseif ($ch -eq "2") {
        $StartStep = "2";  $menuDone = $true
    } elseif ($ch -eq "3") {
        $StartStep = "3";  $menuDone = $true
    } elseif ($ch -eq "A") {
        $StartStep = "1a"; $menuDone = $true
    } elseif ($ch -eq "Q") {
        Write-Host ""; Write-Host "  Goodbye."; exit 0
    } else {
        Write-Host "  Enter 1, 2, 3, A, or Q" -ForegroundColor Yellow
    }
}

# ==============================================================================
# PHASE 4 -- Options
# ==============================================================================
Write-Host ""
HR
Write-Host "  PHASE 4 -- Options" -ForegroundColor White
HR
Write-Host ""

$r = Read-Host "  Max retries for Step 3 [3]"
$MaxRetries = if ($r) { $r } else { "3" }

$l = Read-Host "  Log level (DEBUG/INFO/WARNING) [DEBUG]"
$LogLevel = if ($l) { $l.ToUpper() } else { "DEBUG" }

Write-Host ""
Write-Host "  Use Ollama for translation memory embeddings?"
Write-Host "  Y  -- Real semantic similarity (requires Ollama running locally)"
Write-Host "  N  -- Hash fallback, no Ollama needed (default)"
Write-Host ""

$OllamaEmbedModel = ""
$OllamaBaseUrl    = "http://localhost:11434"
$oeDone = $false

while (-not $oeDone) {
    $oe = (Read-Host "  Use Ollama embeddings? [Y/N] (default N)").ToUpper().Trim()
    if ($oe -eq "Y") {
        $ourl = Read-Host "  Ollama base URL [http://localhost:11434]"
        $OllamaBaseUrl = if ($ourl) { $ourl } else { "http://localhost:11434" }
        $omodel = Read-Host "  Embedding model [nomic-embed-text]"
        $OllamaEmbedModel = if ($omodel) { $omodel } else { "nomic-embed-text" }
        $oeDone = $true
    } elseif ($oe -eq "N" -or $oe -eq "") {
        $OllamaEmbedModel = ""
        $oeDone = $true
    } else {
        Write-Host "  Please enter Y or N" -ForegroundColor Yellow
    }
}

$EmbedDisplay = if ($OllamaEmbedModel) { $OllamaEmbedModel } else { "hash (no Ollama)" }

# ==============================================================================
# Summary & launch
# ==============================================================================
Write-Host ""
HR
Write-Host ""
Write-Host "  Source      : " -NoNewline; Write-Host $SourceDir    -ForegroundColor White
Write-Host "  Output      : " -NoNewline; Write-Host $OutputDir    -ForegroundColor White
Write-Host "  Python      : " -NoNewline; Write-Host $Python       -ForegroundColor White
Write-Host "  Start step  : " -NoNewline; Write-Host $StartStep    -ForegroundColor White
Write-Host "  Max retries : " -NoNewline; Write-Host $MaxRetries   -ForegroundColor White
Write-Host "  Log level   : " -NoNewline; Write-Host $LogLevel     -ForegroundColor White
Write-Host "  Embeddings  : " -NoNewline; Write-Host $EmbedDisplay -ForegroundColor White
Write-Host ""
HR
Write-Host ""

$launchDone = $false
while (-not $launchDone) {
    $go = (Read-Host "  Start migration? [Y/N/Q]").ToUpper().Trim()
    if ($go -eq "Y" -or $go -eq "") {
        $launchDone = $true
    } elseif ($go -eq "N") {
        Write-Host "  Aborted."; exit 0
    } elseif ($go -eq "Q") {
        Write-Host "  Goodbye."; exit 0
    } else {
        Write-Host "  Enter Y, N, or Q" -ForegroundColor Yellow
    }
}

Write-Host ""
Set-Location $ScriptDir

if (-not $Python) {
    Write-Host "  [ERROR] Python not found. Please install Python or activate your conda/venv environment." -ForegroundColor Red
    exit 1
}

$env:OLLAMA_EMBED_MODEL = $OllamaEmbedModel
$env:OLLAMA_BASE_URL    = $OllamaBaseUrl

& $Python main.py $SourceDir `
    --start-step $StartStep `
    --retries    $MaxRetries `
    --log-level  $LogLevel

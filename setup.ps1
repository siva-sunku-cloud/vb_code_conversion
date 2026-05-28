# setup.ps1 -- Windows setup for the Java->Python migration tool
# Run with: powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Stop"
$CONDA_ENV = "vb_migration"
$ENV_FILE  = ".env"

function Info    { param($msg) Write-Host "[INFO]  $msg"  -ForegroundColor Cyan   }
function Success { param($msg) Write-Host "[OK]    $msg"  -ForegroundColor Green  }
function Warn    { param($msg) Write-Host "[WARN]  $msg"  -ForegroundColor Yellow }
function Fail    { param($msg) Write-Host "[ERROR] $msg"  -ForegroundColor Red; exit 1 }

# -- Find conda ----------------------------------------------------------------
$condaExe = $env:CONDA_EXE
if (-not $condaExe) {
    $c = Get-Command conda -ErrorAction SilentlyContinue
    if ($c) { $condaExe = $c.Source }
}

# -- Environment setup --------------------------------------------------------
$USE_CONDA = $false
$PYTHON    = $null

if ($condaExe -and (Test-Path $condaExe)) {
    Info "Conda detected -- using conda environment '$CONDA_ENV'"
    $USE_CONDA = $true

    $envJson = (& $condaExe env list --json 2>&1) -join ""
    $envList = ($envJson | ConvertFrom-Json).envs
    $envPath = $envList | Where-Object { (Split-Path $_ -Leaf) -eq $CONDA_ENV } | Select-Object -First 1

    if ($envPath) {
        Info "Conda env '$CONDA_ENV' already exists -- skipping creation."
    } else {
        Info "Creating conda env '$CONDA_ENV' with Python 3.10..."
        & $condaExe create -y -n $CONDA_ENV python=3.10 2>&1 | Select-Object -Last 3
        Success "Created conda env '$CONDA_ENV'"

        $envJson = (& $condaExe env list --json 2>&1) -join ""
        $envList = ($envJson | ConvertFrom-Json).envs
        $envPath = $envList | Where-Object { (Split-Path $_ -Leaf) -eq $CONDA_ENV } | Select-Object -First 1
    }

    if (-not $envPath) { Fail "Could not locate conda env path for '$CONDA_ENV'" }
    $PYTHON = Join-Path $envPath "python.exe"
    if (-not (Test-Path $PYTHON)) { Fail "python.exe not found in conda env: $envPath" }
    Success "Using conda env '$CONDA_ENV'"

} else {
    Warn "Conda not found -- falling back to Python venv"
    $VENV_DIR = ".venv"

    # Find Python 3.10+ in PATH
    foreach ($cmd in @("python", "python3", "py")) {
        try {
            $ver = & $cmd --version 2>&1
            if ($ver -match "Python (\d+)\.(\d+)") {
                $major = [int]$Matches[1]; $minor = [int]$Matches[2]
                if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                    $PYTHON = $cmd; break
                }
            }
        } catch {}
    }

    # Also check Windows registry (python.org installs not in PATH)
    if (-not $PYTHON) {
        foreach ($regRoot in @("HKCU:\SOFTWARE\Python\PythonCore", "HKLM:\SOFTWARE\Python\PythonCore")) {
            if (-not $PYTHON -and (Test-Path $regRoot)) {
                Get-ChildItem $regRoot -ErrorAction SilentlyContinue | ForEach-Object {
                    if (-not $PYTHON) {
                        $ipPath = Join-Path $_.PSPath "InstallPath"
                        if (Test-Path $ipPath) {
                            $pyDir = (Get-ItemProperty $ipPath -ErrorAction SilentlyContinue)."(default)"
                            if ($pyDir) {
                                $pyExe = Join-Path $pyDir "python.exe"
                                if (Test-Path $pyExe) {
                                    try {
                                        $ver = & $pyExe --version 2>&1
                                        if ($ver -match "Python (\d+)\.(\d+)") {
                                            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
                                            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                                                $PYTHON = $pyExe
                                            }
                                        }
                                    } catch {}
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (-not $PYTHON) {
        Fail "Python 3.10+ not found. Install Miniconda (https://docs.conda.io) or Python (https://python.org) and re-run."
    }

    $pyVer = (& $PYTHON --version 2>&1) -replace "Python ", ""
    Success "Python $pyVer"

    if (-not (Test-Path $VENV_DIR)) {
        Info "Creating virtual environment..."
        & $PYTHON -m venv $VENV_DIR
        Success "Created $VENV_DIR"
    } else {
        Info "Virtual environment already exists -- skipping creation."
    }

    $activateScript = Join-Path $VENV_DIR "Scripts\Activate.ps1"
    if (-not (Test-Path $activateScript)) { Fail "Activation script not found: $activateScript" }
    . $activateScript
    Info "Activated $VENV_DIR"

    $PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"
}

# -- Dependencies --------------------------------------------------------------
Info "Installing dependencies..."
& $PYTHON -m pip install --quiet --upgrade pip
& $PYTHON -m pip install --quiet -r requirements.txt
Success "Dependencies installed."

# -- Provider selection --------------------------------------------------------
Write-Host ""
Write-Host "Select LLM provider:" -ForegroundColor White
Write-Host "  1) Anthropic (claude-sonnet / claude-opus)"
Write-Host "  2) GitHub Copilot (gpt-4o via github/)"
Write-Host "  3) OpenAI (gpt-4o)"
Write-Host ""
$choice = Read-Host "Enter choice [1-3]"

switch ($choice) {
    "1" { $provider = "anthropic"; $keyVar = "ANTHROPIC_API_KEY" }
    "2" { $provider = "copilot";   $keyVar = "GITHUB_COPILOT_TOKEN" }
    "3" { $provider = "openai";    $keyVar = "OPENAI_API_KEY" }
    default { Fail "Invalid choice." }
}

# -- Endpoint selection --------------------------------------------------------
Write-Host ""
Write-Host "Endpoint type:" -ForegroundColor White
Write-Host "  1) Personal  -- provider's standard API endpoint"
Write-Host "  2) Company   -- Azure OpenAI (paste the full endpoint URL)"
Write-Host ""
$endpointChoice = Read-Host "Enter choice [1-2]"

$azureApiBase    = ""
$azureDeployment = ""
$azureApiVersion = ""

if ($endpointChoice -eq "1") {
    $apiKey = Read-Host "API key" -AsSecureString

} elseif ($endpointChoice -eq "2") {
    $provider = "azure"
    $keyVar   = "OPENAI_API_KEY"
    $azureFullUrl = Read-Host "Full Azure endpoint URL"
    if ([string]::IsNullOrWhiteSpace($azureFullUrl)) { Fail "Endpoint URL cannot be empty." }

    if ($azureFullUrl -match 'https://[^/]+')          { $azureApiBase    = $Matches[0] }
    if ($azureFullUrl -match '/deployments/([^/?]+)')  { $azureDeployment = $Matches[1] }
    if ($azureFullUrl -match 'api-version=([^/&]+)')   { $azureApiVersion = $Matches[1] }

    if ([string]::IsNullOrWhiteSpace($azureApiBase))    { Fail "Could not parse Azure base URL -- check the endpoint URL." }
    if ([string]::IsNullOrWhiteSpace($azureDeployment)) { Fail "Could not parse deployment name -- check the endpoint URL." }
    if ([string]::IsNullOrWhiteSpace($azureApiVersion)) { $azureApiVersion = "2025-01-01-preview" }

    Info "Parsed -> base: $azureApiBase  deployment: $azureDeployment  version: $azureApiVersion"
    $apiKey = Read-Host "API key" -AsSecureString

} else {
    Fail "Invalid choice."
}

$plainKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($apiKey)
)
if ([string]::IsNullOrWhiteSpace($plainKey)) { Fail "API key cannot be empty." }

# -- Write .env ----------------------------------------------------------------
Info "Writing $ENV_FILE..."

if ($endpointChoice -eq "2") {
@"
# Auto-generated by setup.ps1 -- edit as needed

LLM_PROVIDER=azure
$keyVar=$plainKey
AZURE_API_BASE=$azureApiBase
AZURE_DEPLOYMENT=$azureDeployment
AZURE_API_VERSION=$azureApiVersion
AGENT_MODEL=azure/$azureDeployment
HUB_MODEL=azure/$azureDeployment

# Optional: Qdrant vector store (leave blank to skip)
# QDRANT_URL=http://localhost:6333
# QDRANT_API_KEY=

# Optional: GitHub integration
# GITHUB_TOKEN=
# GITHUB_REPO=owner/repo
"@ | Set-Content -Encoding UTF8 $ENV_FILE
} else {
@"
# Auto-generated by setup.ps1 -- edit as needed

LLM_PROVIDER=$provider
$keyVar=$plainKey

# Optional: override default models
# AGENT_MODEL=
# HUB_MODEL=

# Optional: Qdrant vector store (leave blank to skip)
# QDRANT_URL=http://localhost:6333
# QDRANT_API_KEY=

# Optional: GitHub integration
# GITHUB_TOKEN=
# GITHUB_REPO=owner/repo
"@ | Set-Content -Encoding UTF8 $ENV_FILE
}

Success ".env written for provider: $provider"

# -- Done ----------------------------------------------------------------------
Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
if ($USE_CONDA) {
    Write-Host "  Activate the environment:  " -NoNewline
    Write-Host "conda activate $CONDA_ENV" -ForegroundColor Cyan
} else {
    Write-Host "  Activate the environment:  " -NoNewline
    Write-Host "$VENV_DIR\Scripts\Activate.ps1" -ForegroundColor Cyan
}
Write-Host "  Switch provider later:     edit " -NoNewline
Write-Host $ENV_FILE -ForegroundColor Cyan
Write-Host "  Run the migration:         " -NoNewline
Write-Host "python main.py migrate sample_java/ --out .\output" -ForegroundColor Cyan
Write-Host ""

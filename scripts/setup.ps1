# ============================================
# MCP Hub - Setup Script (Windows)
# ============================================

# Requires -Version 5.0

$ErrorActionPreference = "Stop"

# Colors
function Write-Info {
    Write-Host "ℹ $args" -ForegroundColor Blue
}

function Write-Success {
    Write-Host "✓ $args" -ForegroundColor Green
}

function Write-Warning {
    Write-Host "⚠ $args" -ForegroundColor Yellow
}

function Write-Error {
    Write-Host "✗ $args" -ForegroundColor Red
}

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "═══════════════════════════════════════" -ForegroundColor Blue
    Write-Host "  $Message" -ForegroundColor Blue
    Write-Host "═══════════════════════════════════════" -ForegroundColor Blue
    Write-Host ""
}

# Check if command exists
function Test-Command {
    param([string]$Command)
    $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

# Main setup
function Main {
    Write-Header "MCP Hub Setup"

    # 1. Check Python version
    Write-Info "Checking Python version..."
    if (-not (Test-Command python)) {
        Write-Error "Python is not installed. Please install Python 3.11 or higher."
        Write-Host "Download from: https://www.python.org/downloads/"
        exit 1
    }

    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python (\d+)\.(\d+)\.(\d+)") {
        $major = [int]$matches[1]
        $minor = [int]$matches[2]

        if (($major -lt 3) -or (($major -eq 3) -and ($minor -lt 11))) {
            Write-Error "Python 3.11+ is required. Found: $pythonVersion"
            exit 1
        }

        Write-Success "Python $pythonVersion found"
    } else {
        Write-Error "Could not determine Python version"
        exit 1
    }

    # 2. Check Docker
    Write-Info "Checking Docker..."
    if (Test-Command docker) {
        $dockerVersion = docker --version
        Write-Success "Docker found: $dockerVersion"
    } else {
        Write-Warning "Docker not found. Docker is optional but recommended for deployment."
        Write-Host "Download from: https://www.docker.com/products/docker-desktop"
    }

    # 3. Check Docker Compose
    Write-Info "Checking Docker Compose..."
    if ((Test-Command docker) -and (docker compose version 2>&1)) {
        $composeVersion = docker compose version --short
        Write-Success "Docker Compose $composeVersion found"
    } else {
        Write-Warning "Docker Compose not found. Required for Docker deployment."
    }

    # 4. Create virtual environment
    Write-Info "Creating virtual environment..."
    if (Test-Path "venv") {
        Write-Warning "Virtual environment already exists. Skipping creation."
    } else {
        python -m venv venv
        Write-Success "Virtual environment created"
    }

    # 5. Activate virtual environment
    Write-Info "Activating virtual environment..."
    & ".\venv\Scripts\Activate.ps1"
    Write-Success "Virtual environment activated"

    # 6. Upgrade pip
    Write-Info "Upgrading pip..."
    python -m pip install --upgrade pip --quiet
    Write-Success "pip upgraded"

    # 7. Install dependencies
    Write-Info "Installing dependencies..."
    if (Test-Path "requirements.txt") {
        pip install -r requirements.txt --quiet
        Write-Success "Dependencies installed"
    } else {
        Write-Error "requirements.txt not found"
        exit 1
    }

    # 8. Install development dependencies
    Write-Info "Installing development dependencies..."
    pip install pytest pytest-asyncio pytest-cov pytest-mock black ruff mypy --quiet
    Write-Success "Development dependencies installed"

    # 9. Setup environment file
    Write-Info "Setting up environment file..."
    if (Test-Path ".env") {
        Write-Warning ".env file already exists. Skipping creation."
        Write-Warning "Please ensure your .env file is properly configured."
    } else {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Write-Success ".env file created from .env.example"
            Write-Warning "Please edit .env file with your WordPress credentials."
        } else {
            Write-Error ".env.example not found"
            exit 1
        }
    }

    # 10. Create logs directory
    Write-Info "Creating logs directory..."
    if (-not (Test-Path "logs")) {
        New-Item -ItemType Directory -Path "logs" | Out-Null
    }
    Write-Success "Logs directory ready"

    # 11. Run tests (optional)
    Write-Info "Running tests..."
    try {
        $testResult = pytest -q 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "All tests passed!"
        } else {
            Write-Warning "Some tests failed. Please check the output above."
        }
    } catch {
        Write-Warning "Could not run tests. pytest may not be available."
    }

    # 12. Final instructions
    Write-Header "Setup Complete!"

    Write-Success "Setup completed successfully!"
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host ""
    Write-Host "1. Edit the .env file with your credentials:"
    Write-Host "   notepad .env" -ForegroundColor Blue
    Write-Host ""
    Write-Host "2. Activate the virtual environment:"
    Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Blue
    Write-Host ""
    Write-Host "3. Run the MCP server:"
    Write-Host "   python src/main.py" -ForegroundColor Blue
    Write-Host ""
    Write-Host "4. Or deploy with Docker:"
    Write-Host "   docker compose up -d" -ForegroundColor Blue
    Write-Host ""
    Write-Host "5. Run tests:"
    Write-Host "   pytest --cov" -ForegroundColor Blue
    Write-Host ""
    Write-Host "For more information, visit:"
    Write-Host "https://github.com/mcphub/mcphub" -ForegroundColor Blue
    Write-Host ""
}

# Run main function
try {
    Main
} catch {
    Write-Error "Setup failed: $_"
    exit 1
}

#!/usr/bin/env bash
# validate-local.sh - Local validation script before submission

set -e

echo "=========================================="
echo "EMAIL TRIAGE OPENENV - LOCAL VALIDATION"
echo "=========================================="

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "✗ Python not found. Please install Python 3.9+"
    exit 1
fi

echo "✓ Python found: $(python --version)"

# Check if required files exist
echo ""
echo "Checking files..."
required_files=(
    "email_triage_env/__init__.py"
    "email_triage_env/models.py"
    "email_triage_env/env.py"
    "email_triage_env/graders.py"
    "email_triage_env/app.py"
    "openenv.yaml"
    "inference.py"
    "Dockerfile"
    "requirements.txt"
    "README.md"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file"
    else
        echo "✗ $file NOT FOUND"
        exit 1
    fi
done

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -e . > /dev/null 2>&1 || pip install -q -r requirements.txt

# Run local tests
echo ""
echo "Running local environment tests..."
python test_local.py

echo ""
echo "=========================================="
echo "✓ ALL LOCAL VALIDATIONS PASSED"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Start API server: python -m uvicorn email_triage_env.app:app --port 8000"
echo "2. Build Docker: docker build -t email-triage ."
echo "3. Test Docker: docker run -p 8000:8000 email-triage"
echo "4. See SUBMISSION_GUIDE.md for HF Spaces deployment"

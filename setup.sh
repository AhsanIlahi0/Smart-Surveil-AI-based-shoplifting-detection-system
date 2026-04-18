#!/bin/bash
set -e

echo ""
echo "═══════════════════════════════════════════════"
echo "  FYP Shoplifting Detection — Local Setup"
echo "═══════════════════════════════════════════════"
echo ""

# ── 1. PostgreSQL ─────────────────────────────────────────────────────────────
echo "[1/4] Setting up PostgreSQL..."

# Install if not present
if ! command -v psql &> /dev/null; then
  sudo pacman -S --noconfirm postgresql
fi

# Init cluster if not done
if [ ! -f /var/lib/postgres/data/PG_VERSION ]; then
  sudo -u postgres initdb -D /var/lib/postgres/data
fi

# Start service
sudo systemctl enable --now postgresql

# Create DB user and database (ignore errors if already exists)
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='fyp_user'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER fyp_user WITH PASSWORD 'fyp_pass';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='fyp_db'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE fyp_db OWNER fyp_user;"

echo "    PostgreSQL ready  ✓"

# ── 2. Python venv ────────────────────────────────────────────────────────────
echo "[2/4] Creating Python virtual environment..."

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "    Python venv ready  ✓"

# ── 3. .env file ──────────────────────────────────────────────────────────────
echo "[3/4] Creating .env file..."
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "    .env created — edit it to add your ngrok URL"
else
  echo "    .env already exists — skipping"
fi

# ── 4. Folders ────────────────────────────────────────────────────────────────
echo "[4/4] Creating folders..."
mkdir -p uploads incidents static
echo "    Folders ready  ✓"

echo ""
echo "═══════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  To start the server:"
echo "    source venv/bin/activate"
echo "    uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "  Then open: http://localhost:8000"
echo ""
echo "  Don't forget to:"
echo "    1. Start your Kaggle kernel"
echo "    2. Paste the ngrok URL into the dashboard header"
echo "═══════════════════════════════════════════════"
echo ""

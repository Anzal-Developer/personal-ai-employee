#!/usr/bin/env bash
# Cloud Setup — AI Employee Platinum Tier
# Installs and configures the cloud agent on Ubuntu (AWS / Oracle Cloud Free VM)
#
# Run once as ubuntu user:
#   chmod +x deploy/cloud_setup.sh && ./deploy/cloud_setup.sh
#
# What this does:
#   1. Install Python 3, pip, git, nginx, certbot
#   2. Install Node.js + PM2 (process manager)
#   3. Clone / update the repo
#   4. Install Python dependencies
#   5. Configure PM2 to start cloud_orchestrator + sync_vault on boot
#   6. Set up nginx reverse proxy for Odoo (port 8069) with SSL (optional)

set -euo pipefail

REPO_URL="https://github.com/Anzal-Developer/personal-ai-employee.git"
REPO_DIR="/home/ubuntu/personal-ai-employee"
DOMAIN=""          # Set to your domain if you have one (for SSL), e.g. ai.yourdomain.com
PM2_NAME_ORCHESTRATOR="cloud-orchestrator"
PM2_NAME_SYNC="vault-sync"

echo "============================================================"
echo "  AI Employee — Cloud Setup (Platinum Tier)"
echo "  AWS Ubuntu VM"
echo "============================================================"

# ── 1. System packages ────────────────────────────────────────────────────────
echo "[1/6] Installing system packages..."
sudo apt-get update -q
sudo apt-get install -y -q python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx curl

# ── 2. Node.js + PM2 ─────────────────────────────────────────────────────────
echo "[2/6] Installing Node.js + PM2..."
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y -q nodejs
fi
sudo npm install -g pm2@latest

# ── 3. Clone / pull repo ──────────────────────────────────────────────────────
echo "[3/6] Setting up repository at $REPO_DIR..."
if [ -d "$REPO_DIR/.git" ]; then
    git -C "$REPO_DIR" pull --rebase origin master
else
    git clone "$REPO_URL" "$REPO_DIR"
fi

# ── 4. Python dependencies ────────────────────────────────────────────────────
echo "[4/6] Installing Python dependencies..."
pip3 install --quiet -r "$REPO_DIR/requirements.txt"

# ── 5. PM2 processes ─────────────────────────────────────────────────────────
echo "[5/6] Starting PM2 processes..."
cd "$REPO_DIR"

# Stop existing if running
pm2 stop "$PM2_NAME_ORCHESTRATOR" 2>/dev/null || true
pm2 stop "$PM2_NAME_SYNC"         2>/dev/null || true
pm2 delete "$PM2_NAME_ORCHESTRATOR" 2>/dev/null || true
pm2 delete "$PM2_NAME_SYNC"         2>/dev/null || true

# vault sync — every 5 minutes via --watch
pm2 start sync_vault.py \
    --interpreter python3 \
    --name "$PM2_NAME_SYNC" \
    -- --watch \
    --update-env

# cloud orchestrator — every 2 minutes via --watch
pm2 start cloud_orchestrator.py \
    --interpreter python3 \
    --name "$PM2_NAME_ORCHESTRATOR" \
    -- --watch \
    --update-env

# gmail watcher — continuous
pm2 start gmail_watcher.py \
    --interpreter python3 \
    --name "gmail-watcher" \
    --update-env

pm2 save
sudo env PATH=$PATH:/usr/bin pm2 startup systemd -u ubuntu --hp /home/ubuntu

echo ""
echo "PM2 processes:"
pm2 list

# ── 6. Nginx reverse proxy for Odoo (optional) ───────────────────────────────
echo "[6/6] Configuring nginx..."
sudo cp "$REPO_DIR/deploy/nginx/odoo-ssl.conf" /etc/nginx/sites-available/odoo
sudo ln -sf /etc/nginx/sites-available/odoo /etc/nginx/sites-enabled/odoo
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

if [ -n "$DOMAIN" ]; then
    echo "  Setting up SSL for $DOMAIN via Let's Encrypt..."
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@"$DOMAIN" || true
fi

echo ""
echo "============================================================"
echo "  Setup complete!"
echo ""
echo "  Cloud processes running:"
echo "    - gmail-watcher       (monitors Gmail)"
echo "    - cloud-orchestrator  (claims + drafts, every 2 min)"
echo "    - vault-sync          (Git pull/push, every 5 min)"
echo ""
echo "  IMPORTANT: Upload secrets manually (never via Git):"
echo "    scp -i hackathon.pem credentials.json ubuntu@<IP>:$REPO_DIR/"
echo "    scp -i hackathon.pem gmail_token.json  ubuntu@<IP>:$REPO_DIR/"
echo ""
echo "  Monitor: pm2 logs | pm2 monit"
echo "  Health:  python3 cloud_orchestrator.py --health"
echo "============================================================"

#!/bin/bash
# Multi-Echelon Bypass Setup Script for Ubuntu 20.04 / 22.04 / 24.04
# Author: Automated Bypass Kit
set -euo pipefail

echo "=== [1/6] System Optimization (BBR + Swap) ==="
# BBR setup
if ! grep -q "net.core.default_qdisc=fq" /etc/sysctl.conf; then
    echo "net.core.default_qdisc=fq" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.conf
    sysctl -p
fi

# 2GB Swap setup if no swap exists
if [ $(swapon --show | wc -l) -le 1 ]; then
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "=== [2/6] Base Dependencies ==="
apt update && apt install -y curl wget git jq ufw unzip socat python3 python3-pip

echo "=== [3/6] Install 3X-UI (Xray Core) ==="
if [ ! -d "/etc/x-ui" ]; then
    bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)
fi

echo "=== [4/6] Install Hysteria 2 ==="
if ! command -v hysteria &> /dev/null; then
    bash <(curl -fsSL https://get.hy2.sh/)
fi

echo "=== [5/6] Install Tunnel Agents (Zrok, Playit, Tailscale) ==="
# Zrok
if ! command -v zrok &> /dev/null; then
    curl -sSL https://get.zrok.io | bash
fi

# Playit.gg
if ! command -v playit &> /dev/null; then
    curl -SsL https://playit-cloud.github.io/ppa/key.gpg | gpg --dearmor -o /etc/apt/trusted.gpg.d/playit.gpg
    echo "deb [signed-by=/etc/apt/trusted.gpg.d/playit.gpg] https://playit-cloud.github.io/ppa/data ./" | tee /etc/apt/sources.list.d/playit.list
    apt update && apt install -y playit || {
        echo "Using direct playit binary fallback..."
        PLAYIT_URL=$(curl -s https://api.github.com/repos/playit-cloud/playit-agent/releases/latest | jq -r '.assets[] | select(.name | contains("x86_64") and endswith(".deb") | not and contains("linux")) | .browser_download_url' | head -n 1)
        curl -Lo /usr/local/bin/playit "$PLAYIT_URL" && chmod +x /usr/local/bin/playit
    }
fi

# Tailscale
if ! command -v tailscale &> /dev/null; then
    curl -fsSL https://tailscale.com/install.sh | sh
fi

echo "=== [6/6] Firewall Configuration ==="
ufw allow 22/tcp || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
ufw allow 2053/tcp || true
ufw allow 2054/tcp || true
ufw allow 8080/tcp || true
ufw allow 20443/udp || true

echo "=== Setup complete! Proceed with configuring credentials and inbounds. ==="

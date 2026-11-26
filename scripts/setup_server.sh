#!/bin/bash
# Multi-Echelon VPS Network Kit Setup Script for Ubuntu 20.04 / 22.04 / 24.04
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== [1/6] System Optimization (BBR + Swap) ==="
if ! grep -q "net.core.default_qdisc=fq" /etc/sysctl.conf; then
    echo "net.core.default_qdisc=fq" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.conf
    sysctl -p
fi

if [ "$(swapon --show | wc -l)" -le 1 ]; then
    fallocate -l 1G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=1024
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "=== [2/6] Base Dependencies ==="
apt-get update && apt-get install -y curl wget git jq ufw unzip socat openssl python3

echo "=== [3/6] Install 3X-UI (Xray Core) ==="
if [ ! -d "/etc/x-ui" ]; then
    bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)
fi

echo "=== [4/6] Install Hysteria 2 & Management Panel ==="
if ! command -v hysteria &> /dev/null; then
    bash <(curl -fsSL https://get.hy2.sh/)
fi

mkdir -p /etc/hysteria /opt/hysteria-panel
if [ ! -f /etc/hysteria/server.crt ]; then
    openssl req -x509 -nodes -newkey ec:<(openssl ecparam -name prime256v1) \
        -keyout /etc/hysteria/server.key \
        -out /etc/hysteria/server.crt \
        -subj "/CN=bing.com" -days 3650
fi

[ -f /etc/hysteria/config.yaml ] || cp "$REPO_DIR/configs/hysteria-config.yaml" /etc/hysteria/config.yaml
cp "$REPO_DIR/configs/hysteria-panel/app.py" /opt/hysteria-panel/app.py

echo "=== [5/6] Install Tunnel Agents (zrok2, Playit.gg, Tailscale) ==="
if ! command -v zrok2 &> /dev/null; then
    TMP_DIR="$(mktemp -d)"
    ZROK_VERSION="$(curl -sSf https://api.github.com/repos/openziti/zrok/releases/latest | jq -r '.tag_name')"
    case "$(uname -m)" in
        x86_64)  GOXARCH="amd64" ;;
        aarch64|arm64) GOXARCH="arm64" ;;
        *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
    esac
    curl -sSfL "https://github.com/openziti/zrok/releases/download/${ZROK_VERSION}/zrok2_${ZROK_VERSION#v}_linux_${GOXARCH}.tar.gz" \
        | tar -xz -C "$TMP_DIR"
    install -o root -g root -m 0755 "$TMP_DIR/zrok2" /usr/local/bin/zrok2
    rm -rf "$TMP_DIR"
fi

if ! command -v playit &> /dev/null; then
    curl -SsL https://playit-cloud.github.io/ppa/key.gpg | gpg --dearmor --yes -o /etc/apt/trusted.gpg.d/playit.gpg
    echo "deb [signed-by=/etc/apt/trusted.gpg.d/playit.gpg] https://playit-cloud.github.io/ppa/data ./" | tee /etc/apt/sources.list.d/playit.list
    apt-get update && apt-get install -y playit || {
        echo "Using direct playit binary fallback..."
        PLAYIT_URL="$(curl -sSf https://api.github.com/repos/playit-cloud/playit-agent/releases/latest \
            | jq -r '.assets[] | select((.name | test("linux")) and (.name | test("amd64|x86_64")) and (.name | endswith(".deb") | not)) | .browser_download_url' \
            | head -n 1)"
        curl -sSfL -o /usr/local/bin/playit "$PLAYIT_URL" && chmod +x /usr/local/bin/playit
    }
fi

if ! command -v tailscale &> /dev/null; then
    curl -fsSL https://tailscale.com/install.sh | sh
fi

echo "=== [6/6] Install Systemd Templates & Firewall Rules ==="
for unit in hysteria-server.service hysteria-panel.service zrok2-tunnel.service playit.service; do
    if [ ! -f "/etc/systemd/system/$unit" ]; then
        cp "$REPO_DIR/configs/systemd/$unit" "/etc/systemd/system/$unit"
    fi
done
systemctl daemon-reload

ufw allow 22/tcp || true
ufw allow 443/tcp || true
ufw allow 2053/tcp || true
ufw allow 2054/tcp || true
ufw allow 8080/tcp || true
ufw allow 25652/tcp || true
ufw allow 20443/udp || true

echo "=== Setup complete! ==="
echo "Next:"
echo "  1. Configure 3X-UI inbounds (443 Reality + 8080 WS /vless) via https://<VPS_IP>:2053"
echo "  2. Customize secrets in /etc/hysteria/config.yaml and /etc/systemd/system/hysteria-panel.service"
echo "  3. Enable tunnels: zrok2 enable <TOKEN>, playit setup, tailscale up && tailscale funnel --bg --https=8443 http://127.0.0.1:8080"

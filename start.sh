#!/bin/bash

echo "=== Kola Backend Startup ==="

PORT=${PORT:-8000}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Download pre-built binaries to /tmp/ (writable at runtime) ---

# Node.js (for yt-dlp JS challenge solving)
if [ ! -f /tmp/node-v20.18.0-linux-x64/bin/node ]; then
  echo "Downloading Node.js..."
  curl -fsSL -o /tmp/node.tar.xz https://nodejs.org/dist/v20.18.0/node-v20.18.0-linux-x64.tar.xz && \
  tar -xf /tmp/node.tar.xz -C /tmp/ && \
  echo "Node.js ready" || echo "WARNING: Node.js download failed"
fi

# wgcf (WARP credential generator)
if [ ! -f /tmp/wgcf ]; then
  echo "Downloading wgcf..."
  curl -fsSL -o /tmp/wgcf https://github.com/ViRb3/wgcf/releases/download/v2.2.22/wgcf_2.2.22_linux_amd64 && \
  chmod +x /tmp/wgcf && \
  echo "wgcf ready" || echo "WARNING: wgcf download failed"
fi

# wireproxy (WireGuard userspace -> SOCKS5)
if [ ! -f /tmp/wireproxy ]; then
  echo "Downloading wireproxy..."
  curl -fsSL -o /tmp/wireproxy.tar.gz https://github.com/windtf/wireproxy/releases/download/v1.1.2/wireproxy_linux_amd64.tar.gz
  tar -xzf /tmp/wireproxy.tar.gz -C /tmp/ && \
  find /tmp -name wireproxy -type f -exec chmod +x {} \; -exec mv {} /tmp/wireproxy \; && \
  echo "wireproxy ready" || echo "WARNING: wireproxy download failed"
fi

# --- Add Node.js to PATH ---
export PATH="/tmp/node-v20.18.0-linux-x64/bin:$PATH"

# --- Start WARP proxy ---
if [ -f /tmp/wgcf ] && [ -f /tmp/wireproxy ]; then
  echo "Generating WARP config..."
  rm -f /tmp/wgcf-profile.conf
  cd /tmp
  /tmp/wgcf register --accept-tos 2>&1 || true
  /tmp/wgcf generate 2>&1 || true

  if [ -f /tmp/wgcf-profile.conf ]; then
    printf '\n[Socks5]\nBindAddress = 127.0.0.1:1080\n' >> /tmp/wgcf-profile.conf

    echo "Starting wireproxy..."
    /tmp/wireproxy -c /tmp/wgcf-profile.conf &
    WARP_PID=$!
    sleep 3

    if kill -0 $WARP_PID 2>/dev/null; then
      echo "WARP proxy started on 127.0.0.1:1080"
    else
      echo "WARNING: WARP proxy failed to start"
    fi
  else
    echo "WARNING: WARP config not generated"
  fi
else
  echo "WARNING: WARP dependencies missing, continuing without proxy"
fi

# --- Start uvicorn ---
echo "Starting uvicorn on port $PORT..."
cd "$SCRIPT_DIR"
exec uvicorn main:app --host 0.0.0.0 --port $PORT

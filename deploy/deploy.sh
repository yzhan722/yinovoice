#!/bin/bash
# ============================================================================
# YinoVapi 一键部署脚本（8.215.80.82）
# 用法：在服务器上以 root 执行  bash deploy.sh
# 前置：已 SCP 上传整个 deploy-package/ 目录到服务器任意路径
# ============================================================================
set -euo pipefail

APP_DIR=/opt/yino-vapi
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "  YinoVapi 一键部署（8.215.80.82）"
echo "  源目录: $SRC_DIR"
echo "  目标目录: $APP_DIR"
echo "=========================================="
echo ""

# ---------- [1/9] 创建目录 ----------
echo "[1/9] 创建目录..."
mkdir -p "$APP_DIR"/{certs,config,data/recordings,bin,logs}

# ---------- [2/9] 复制源码与配置 ----------
echo "[2/9] 复制源码与配置..."
cp -r "$SRC_DIR/src/platform-api" "$APP_DIR/"
cp -r "$SRC_DIR/src/voice-agent" "$APP_DIR/"
cp -r "$SRC_DIR/src/frontend-dist" "$APP_DIR/"
cp -r "$SRC_DIR/config/"* "$APP_DIR/config/"
cp -r "$SRC_DIR/systemd" "$APP_DIR/"

# ---------- [3/9] 生成自签名证书 ----------
echo "[3/9] 生成自签名证书..."
if [[ ! -f "$APP_DIR/certs/fullchain.pem" ]]; then
  openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -keyout "$APP_DIR/certs/privkey.pem" \
    -out "$APP_DIR/certs/fullchain.pem" \
    -subj "/CN=8.215.80.82/O=YinoVapi/C=CN"
  chmod 600 "$APP_DIR/certs/privkey.pem"
  echo "  证书已生成"
else
  echo "  证书已存在，跳过"
fi

# ---------- [4/9] 生成 LiveKit 强密钥并替换占位符 ----------
echo "[4/9] 生成 LiveKit 密钥..."
if grep -q "CHANGE_ME_API_KEY" "$APP_DIR/config/platform-api.env"; then
  API_KEY=$(openssl rand -hex 16)
  API_SECRET=$(openssl rand -hex 32)
  sed -i "s/CHANGE_ME_API_KEY/$API_KEY/g" "$APP_DIR/config/platform-api.env"
  sed -i "s/CHANGE_ME_API_SECRET/$API_SECRET/g" "$APP_DIR/config/platform-api.env"
  sed -i "s/CHANGE_ME_API_KEY/$API_KEY/g" "$APP_DIR/config/voice-agent.env"
  sed -i "s/CHANGE_ME_API_SECRET/$API_SECRET/g" "$APP_DIR/config/voice-agent.env"
  # LiveKit yaml 使用 keys: map 格式（不是 api_key/api_secret）
  cat > "$APP_DIR/config/livekit.yaml" <<EOF
port: 7880
bind_addresses: ["0.0.0.0"]
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: true
keys:
  ${API_KEY}: ${API_SECRET}
room:
  auto_create: true
  empty_timeout: 300
  enable_remote_unmute: true
logging:
  level: info
EOF
  echo "  密钥已生成并注入"
else
  echo "  密钥已存在，跳过"
fi

# ---------- [5/9] 安装 uv 并创建 Python 虚拟环境 ----------
echo "[5/9] 安装 Python 环境..."
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# platform-api venv
cd "$APP_DIR/platform-api"
if [[ ! -x .venv/bin/python ]]; then
  uv python install 3.12
  uv venv --python 3.12 .venv
fi
uv pip install --python .venv/bin/python -e .
echo "  platform-api 依赖已安装"

# voice-agent venv
cd "$APP_DIR/voice-agent"
if [[ ! -x .venv/bin/python ]]; then
  uv venv --python 3.12 .venv
fi
uv pip install --python .venv/bin/python -e .
echo "  voice-agent 依赖已安装"

# ---------- [6/9] 下载 LiveKit Server ----------
echo "[6/9] 下载 LiveKit Server..."
if [[ ! -f "$APP_DIR/bin/livekit-server" ]] || [[ $(wc -c < "$APP_DIR/bin/livekit-server") -lt 1000000 ]]; then
  LK_VERSION=v1.8.3
  LK_TGZ="livekit_1.8.3_linux_amd64.tar.gz"
  echo "  下载 livekit-server $LK_VERSION (linux-amd64 tarball)..."
  tmpdir=$(mktemp -d)
  curl -fL --retry 3 \
    "https://github.com/livekit/livekit/releases/download/$LK_VERSION/$LK_TGZ" \
    -o "$tmpdir/livekit.tgz"
  tar -xzf "$tmpdir/livekit.tgz" -C "$tmpdir"
  install -m 755 "$(find "$tmpdir" -type f -name livekit-server | head -1)" \
    "$APP_DIR/bin/livekit-server"
  rm -rf "$tmpdir"
  echo "  下载完成 ($(wc -c < "$APP_DIR/bin/livekit-server") bytes)"
else
  echo "  已存在，跳过"
fi

# ---------- [7/9] 安装 systemd 服务 ----------
echo "[7/9] 安装 systemd 服务..."
cp "$APP_DIR/systemd/"*.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable yino-livekit yino-platform-api yino-voice-agent

systemctl restart yino-livekit
sleep 3
systemctl restart yino-platform-api
sleep 3
systemctl restart yino-voice-agent
sleep 2
echo "  三个服务已启动"

# ---------- [8/9] 配置 nginx ----------
echo "[8/9] 配置 nginx..."
if [[ -d /www/server/panel/vhost/nginx ]]; then
  cp "$APP_DIR/config/nginx-yino-vapi.conf" /www/server/panel/vhost/nginx/yino-vapi-443.conf
  echo "  宝塔面板 nginx 配置已安装"
elif [[ -d /etc/nginx/conf.d ]]; then
  cp "$APP_DIR/config/nginx-yino-vapi.conf" /etc/nginx/conf.d/yino-vapi.conf
  echo "  nginx 配置已安装到 /etc/nginx/conf.d/"
else
  echo "  [警告] 未找到 nginx 配置目录，请手动安装 $APP_DIR/config/nginx-yino-vapi.conf"
fi
nginx -t && nginx -s reload
echo "  nginx 已 reload"

# ---------- [9/9] 验证 ----------
echo "[9/9] 验证服务..."
sleep 2
echo ""
echo "  LiveKit:       $(systemctl is-active yino-livekit)"
echo "  Platform API:  $(systemctl is-active yino-platform-api)"
echo "  Voice Agent:   $(systemctl is-active yino-voice-agent)"
echo ""

# 测试 Platform API
if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "  Platform API /health: OK"
else
  echo "  [警告] Platform API /health 不可达，请检查日志:"
  echo "    journalctl -u yino-platform-api -n 50"
fi

# 测试 LiveKit
if curl -sf http://127.0.0.1:7880 >/dev/null 2>&1; then
  echo "  LiveKit Server: OK"
else
  echo "  [警告] LiveKit Server 不可达，请检查日志:"
  echo "    journalctl -u yino-livekit -n 50"
fi

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "  访问地址:  https://8.215.80.82"
echo "  登录账号:  demo / demo123"
echo ""
echo "  阿里云安全组必须放行（如未放行通话将无声音）:"
echo "    443/TCP           (HTTPS)"
echo "    7880/TCP          (LiveKit 信令)"
echo "    50000-60000/UDP   (LiveKit RTC 媒体流)"
echo ""
echo "  首次访问浏览器会提示\"不安全\"，点\"高级 → 继续访问\"即可"
echo ""
echo "  查看服务状态:"
echo "    systemctl status yino-livekit yino-platform-api yino-voice-agent"
echo ""
echo "  查看日志:"
echo "    journalctl -u yino-voice-agent -f"
echo ""

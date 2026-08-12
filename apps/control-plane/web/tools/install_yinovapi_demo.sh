#!/bin/bash
# 在宝塔「终端」或已能 SSH 的机器上执行本脚本
# 用法: bash install_yinovapi_demo.sh
set -euo pipefail

PORT="${BT_HTTP_PORT:-38427}"
REMOTE_DIR="${BT_REMOTE_DIR:-/www/wwwroot/yinovapi-demo}"
SITE_CONF="/www/server/panel/vhost/nginx/yinovapi-demo.conf"
TAR_URL="${1:-}"   # 可选：http(s) 上的 tar 包；否则要求同目录有 yinovapi-demo.tar.gz

mkdir -p "$REMOTE_DIR" /www/wwwlogs /www/server/panel/vhost/nginx

if [[ -n "$TAR_URL" ]]; then
  curl -fsSL "$TAR_URL" -o /tmp/yinovapi-demo.tar.gz
elif [[ -f ./yinovapi-demo.tar.gz ]]; then
  cp ./yinovapi-demo.tar.gz /tmp/yinovapi-demo.tar.gz
else
  echo "缺少 yinovapi-demo.tar.gz，请先上传到当前目录或传入下载 URL"
  exit 1
fi

rm -rf "${REMOTE_DIR:?}/"*
tar -xzf /tmp/yinovapi-demo.tar.gz -C "$REMOTE_DIR"
rm -f /tmp/yinovapi-demo.tar.gz

cat > "$SITE_CONF" <<EOF
server {
    listen ${PORT};
    listen [::]:${PORT};
    server_name _;
    root ${REMOTE_DIR};
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?)$ {
        expires 7d;
        add_header Cache-Control "public";
        try_files \$uri =404;
    }

    access_log /www/wwwlogs/yinovapi-demo.access.log;
    error_log  /www/wwwlogs/yinovapi-demo.error.log;
}
EOF

# 放行端口（宝塔 / firewalld / iptables）
if command -v bt >/dev/null 2>&1; then
  bt 10 "$PORT" >/dev/null 2>&1 || true
fi
firewall-cmd --permanent --add-port="${PORT}/tcp" >/dev/null 2>&1 || true
firewall-cmd --reload >/dev/null 2>&1 || true
iptables -C INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null \
  || iptables -I INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null || true

NGINX_BIN="/www/server/nginx/sbin/nginx"
if [[ -x "$NGINX_BIN" ]]; then
  "$NGINX_BIN" -t
  "$NGINX_BIN" -s reload
else
  nginx -t && (systemctl reload nginx || service nginx reload)
fi

echo "==== listening ===="
ss -lntp | grep ":${PORT}" || true
echo "OK: http://$(curl -s ifconfig.me 2>/dev/null || echo SERVER_IP):${PORT}/#/login"
echo "Demo: demo / demo123"
echo "注意：还需在阿里云安全组放行 TCP ${PORT}"

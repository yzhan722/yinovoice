# YinoVapi 部署到 8.215.80.82 — 操作说明

## 目标
浏览器访问 `https://8.215.80.82` → 登录 → 点通话 → 与 AI 语音对话。

## 架构
```
浏览器 (https://8.215.80.82)
  │
nginx :443 (自签名 HTTPS)
  ├─ /            → 前端 dist (静态)
  ├─ /api/v1/     → platform-api (127.0.0.1:8000)
  └─ /livekit     → LiveKit Server (127.0.0.1:7880, WebSocket)
                     │
                     └─ voice-agent (LiveKit worker, 注册名 yino-customer-service)
                            └─ 直连 Qwen Audio Realtime (wss://dashscope.aliyuncs.com)
```

## 前置条件
- 服务器 8.215.80.82 阿里云 ECS，root 权限
- 已装 nginx（宝塔面板自带或独立安装）
- 服务器能访问外网（下载 uv、LiveKit 二进制、DashScope）

---

## 一、上传部署包到服务器

在本地 Windows（PowerShell）执行：

```powershell
# 方式1：用 scp 上传整个 deploy-package
scp -r D:\project\yinoai\YinoVapi\deploy-package root@8.215.80.82:/root/

# 方式2：先打包再传（更稳）
cd D:\project\yinoai\YinoVapi
tar -czf deploy-package.tar.gz deploy-package
scp deploy-package.tar.gz root@8.215.80.82:/root/
# 在服务器上解压
# ssh root@8.215.80.82
# tar -xzf /root/deploy-package.tar.gz -C /root/
```

---

## 二、在服务器执行一键部署

SSH 登录服务器后执行：

```bash
cd /root/deploy-package
bash deploy.sh
```

脚本会自动完成 9 步：
1. 创建 `/opt/yino-vapi` 目录结构
2. 复制源码、前端、配置到 `/opt/yino-vapi`
3. 生成自签名 HTTPS 证书（825 天有效期）
4. 生成强随机 LiveKit API key/secret 并注入配置
5. 安装 Python 3.12 + uv + 两个 venv + 依赖
6. 下载 LiveKit Server Linux 二进制（v1.8.3）
7. 安装并启动 3 个 systemd 服务
8. 安装 nginx 站点配置并 reload
9. 验证服务状态

---

## 三、配置阿里云安全组（关键！）

登录阿里云控制台 → ECS 实例 8.215.80.82 → 安全组 → 入方向，添加规则：

| 端口范围 | 协议 | 授权对象 | 说明 |
|----------|------|----------|------|
| 443/443 | TCP | 0.0.0.0/0 | HTTPS 入口 |
| 7880/7880 | TCP | 0.0.0.0/0 | LiveKit 信令 |
| 50000/60000 | UDP | 0.0.0.0/0 | LiveKit RTC 媒体流 |

**⚠️ 不放行 UDP 50000-60000 会导致：能连上但无声音**

---

## 四、验证

1. 浏览器访问 `https://8.215.80.82`
2. 看到"不安全"警告 → 点"高级" → "继续访问 8.215.80.82 (不安全)"
3. 登录页输入 `demo` / `demo123`
4. 进入"实时语音"页面
5. 点"开始通话"，浏览器弹出麦克风权限 → 允许
6. 听到 AI 问候："您好，这里是演示机构客服，请问有什么可以帮您？"
7. 说话，AI 回应

---

## 五、常见问题

### Q1: 浏览器无法访问
```bash
# 检查服务
systemctl status yino-livekit yino-platform-api yino-voice-agent
# 检查 nginx
nginx -t
systemctl status nginx
# 检查端口
ss -tlnp | grep -E '443|8000|7880'
```

### Q2: 能连上但无声音
- 检查阿里云安全组 UDP 50000-60000 是否放行
- 浏览器控制台 F12 看是否有 WebRTC ICE 错误
- LiveKit 日志：`journalctl -u yino-livekit -f`

### Q3: 通话建立但 AI 不说话
- 检查 voice-agent 是否注册成功：
  `journalctl -u yino-voice-agent -f` 应看到 "registered worker"
- 检查 DashScope 密钥：服务器能访问 `wss://dashscope.aliyuncs.com`
- 测试：`curl -I https://dashscope.aliyuncs.com`

### Q4: 前端报错 "无法获取安全连接凭据"
- platform-api 没启动：`systemctl restart yino-platform-api`
- 看 platform-api 日志：`journalctl -u yino-platform-api -n 50`
- 测试 API：`curl http://127.0.0.1:8000/health` 应返回 `{"status":"ok"}`

### Q5: nginx 配置冲突
- 宝塔面板可能已有 443 端口占用，需在面板"网站"里停用冲突站点
- 或修改 `nginx-yino-vapi.conf` 的 listen 端口为其他（如 8443）

---

## 六、服务管理

```bash
# 重启所有服务
systemctl restart yino-livekit yino-platform-api yino-voice-agent

# 查看状态
systemctl status yino-livekit yino-platform-api yino-voice-agent

# 实时日志
journalctl -u yino-voice-agent -f
journalctl -u yino-platform-api -f
journalctl -u yino-livekit -f

# 停止服务
systemctl stop yino-voice-agent yino-platform-api yino-livekit
```

---

## 七、文件位置

| 路径 | 说明 |
|------|------|
| `/opt/yino-vapi/` | 应用根目录 |
| `/opt/yino-vapi/frontend-dist/` | 前端静态文件 |
| `/opt/yino-vapi/platform-api/` | Platform API 源码 + venv |
| `/opt/yino-vapi/voice-agent/` | Voice Agent 源码 + venv |
| `/opt/yino-vapi/bin/livekit-server` | LiveKit 二进制 |
| `/opt/yino-vapi/config/` | 配置文件（含已注入密钥的 .env） |
| `/opt/yino-vapi/certs/` | 自签名证书 |
| `/opt/yino-vapi/data/recordings/` | 通话录音（如启用） |
| `/etc/systemd/system/yino-*.service` | systemd 服务 |
| `/www/server/panel/vhost/nginx/yino-vapi-443.conf` | nginx 配置（宝塔） |

---

## 八、注意事项

1. **内存存储**：当前是 InMemory repo，服务器重启数据丢失（demo 阶段可接受）
2. **自签名证书**：每次浏览器会警告，点继续访问即可；如需正式证书请绑定域名
3. **DashScope 密钥**：已硬编码在 `voice-agent.env` 中（`sk-e8e1e290...`），生产环境应改用更安全的方式
4. **LiveKit UDP 端口**：必须放行 50000-60000/UDP，否则无声音
5. **重跑脚本**：`bash deploy.sh` 可重复执行，已存在的证书/密钥会跳过

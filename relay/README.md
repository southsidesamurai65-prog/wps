# Relay — LLM 中转反代（Caddy 单文件）

公网 HTTPS 反代：调用方带 relay token 来 → Caddy 校验 token → 把 `Authorization` 换成真实后端 key → 透传到真实后端 → 原样返回响应。

**真实后端的 URL 和 key 只在本机环境变量里，调用方看不到**；调用方只知道 relay 域名（URL）+ relay token（key）。

## 为什么用 Caddy

公网 HTTPS 用 Python 要自己管证书（或前面再挂个 Caddy/nginx 当 TLS 终端），等于还是要 Caddy；Caddy 一个文件就搞定 HTTPS（自动签证书 + 续期）+ token 校验 + key 注入 + 单后端透传，零 certbot、零 Python。以后真要加自定义逻辑（多后端路由 / 日志细化 / 限流），再在 Caddy 后挂个 Python（FastAPI + httpx）backend，Caddy 当 TLS 终端不变。

## 前置

- 一台公网服务器（Linux VPS，或有端口转发的自家机器）。
- 一个 A 记录指向该服务器的域名（如 `relay.your-domain.com`）。
- 服务器开放 **80 + 443**（Caddy 用 80 做 ACME 验证、443 提供服务）。
- Caddy：单二进制。`apt install caddy` 或从 https://caddyserver.com/download 下官方二进制。

## 部署

```bash
cd relay/
cp .env.example .env
# 编辑 .env：填 RELAY_DOMAIN / RELAY_TOKEN / REAL_KEY / REAL_BASE_URL

# 让 .env 里的变量进环境，再跑 Caddy（前台试跑）
set -a; . ./.env; set +a
caddy run --config Caddyfile
# 首次启动 Caddy 会自动向 Let's Encrypt 申请证书（域名已指向本机、80/443 开放即可）。
```

生产用 systemd（Debian/Ubuntu 的 `apt install caddy` 自带 `caddy.service`）：

```bash
sudo mkdir -p /etc/caddy
sudo cp Caddyfile /etc/caddy/Caddyfile
sudo cp .env /etc/caddy/.env
# /etc/systemd/system/caddy.service 或用 override 指定 config + env：
#   [Service]
#   EnvironmentFile=/etc/caddy/.env
#   ExecStart=/usr/bin/caddy run --config /etc/caddy/Caddyfile
sudo systemctl daemon-reload
sudo systemctl enable --now caddy
sudo systemctl status caddy
```

## 烟测

```bash
# 在服务器或任何能访问 relay 的机器上
./smoke.sh https://relay.your-domain.com "$RELAY_TOKEN"
# 期望：带 token → 200 + choices[0].message.content；不带/错 → 401
```

## 给别人用

把 **`RELAY_DOMAIN`** 和 **`RELAY_TOKEN`** 给对方（不给真实 key）。对方在 wps_tool 这边：

```ini
# wps_tool 的 .env
ENABLE_API_UPLOAD=true
LLM_PROVIDER=openai
LLM_BASE_URL=https://relay.your-domain.com   # relay 域名
LLM_API_KEY=relay-发给你的-token             # relay token（不是真实 key）
LLM_MODEL=gpt-4o
```

wps_tool **零代码改动**——`PptBeautifyClient` 本来就按 `LLM_BASE_URL` + `Authorization: Bearer {LLM_API_KEY}` 发请求，relay 链路天然兼容。

## 安全

- `REAL_KEY` 只在服务器；`relay/.env` 不进 git（根 `.gitignore` 已忽略 `.env`）。
- token 泄了：换一个 `RELAY_TOKEN` → 重启 Caddy。
- 限流：Caddy 的 `rate_limit` 需 [caddy-ratelimit](https://github.com/mholt/caddy-ratelimit) 模块；或直接在后端侧限额度。
- 访问日志：`/var/log/caddy/relay.log`（JSON 格式，可接 ELK / loki）。
- 最小暴露面：relay 只放行 `Authorization` 命中 token 的请求，其余 401。

## 排错

| 现象 | 排查 |
|---|---|
| 证书签不下 | 域名 A 记录是否指向本机公网 IP；80/443 是否开放（防火墙 / 安全组）；`caddy` 进程是否有 80/443 权限。 |
| 200 但后端报错（如 model 不存在 / 401） | relay 透传没问题，问题在后端：查 `REAL_KEY` / `REAL_BASE_URL` / `model` 是否对得上后端。 |
| 后端 403 / Host 拒绝 | 在 `reverse_proxy` 块加 `header_up Host {http.reverse_proxy.upstream.hostport}`（或写死后端 host）。 |
| 带 token 仍 401 | `RELAY_TOKEN` 两边是否一致（Caddyfile 读的是环境变量，确认 systemd / shell 里 export 了）。 |
| Caddy 报 `{$RELAY_TOKEN}` 没替换 | 运行前没 export 变量；`set -a; . ./.env; set +a` 或 systemd `EnvironmentFile`。 |

## 扩展

- **多后端路由**：加多个 `@model` matcher 按 body 里的 `model` 字段路由到不同 `reverse_proxy`（用 Caddy 的 `map` + `expression`）。
- **自定义逻辑**（日志 / 改写 / 鉴权复杂）：在 Caddy 后挂个 Python（FastAPI + httpx）backend，`reverse_proxy localhost:8000`，Caddy 仍当 TLS 终端。
- **多 token / 用户区分**：用 `@valid` 的多值或 `map` 给不同 token 打不同标签，日志区分调用方。

#!/usr/bin/env bash
# relay 烟测：带正确 token → 200 + OpenAI envelope（choices[0].message.content）；
#             不带 / 错 token → 401。
#
# 用法: ./smoke.sh <relay_url> <relay_token>
# 例:   ./smoke.sh https://relay.example.com my-secret-token
#
# 注：用最小请求体 {model, messages}（不带 response_format，relay 只管透传）。
#     若你的真实后端模型名不同，改下面的 BODY 里的 model。

set -uo pipefail

RELAY_URL="${1:-}"
TOKEN="${2:-}"

if [[ -z "$RELAY_URL" || -z "$TOKEN" ]]; then
    echo "用法: $0 <relay_url> <relay_token>" >&2
    exit 2
fi

EP="${RELAY_URL%/}/v1/chat/completions"
BODY='{"model":"gpt-4o","messages":[{"role":"user","content":"ping"}]}'
TMP_RESP="$(mktemp)"
trap 'rm -f "$TMP_RESP"' EXIT

ok=0
fail=0
check() {  # check <label> <got> <want>
    local label="$1" got="$2" want="$3"
    if [[ "$got" == "$want" ]]; then
        echo "  ✓ $label → $got"
        ok=$((ok + 1))
    else
        echo "  ✗ $label → $got（期望 $want）"
        fail=$((fail + 1))
    fi
}

echo "== 1) 带正确 token → 期望 200 + OpenAI envelope =="
code=$(curl -sS -o "$TMP_RESP" -w "%{http_code}" \
    -X POST "$EP" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$BODY" || true)
echo "   status=$code"
check "带 token" "$code" "200"
if [[ "$code" == "200" ]]; then
    if python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); c=d["choices"][0]["message"]["content"]; sys.exit(0 if c is not None else 1)' "$TMP_RESP" 2>/dev/null; then
        echo "   ✓ 响应含 choices[0].message.content"
        ok=$((ok + 1))
    else
        echo "   ✗ 200 但响应不像 OpenAI envelope（前 300 字节）："
        head -c 300 "$TMP_RESP"; echo
        fail=$((fail + 1))
    fi
fi

echo "== 2) 不带 token → 期望 401 =="
code=$(curl -sS -o /dev/null -w "%{http_code}" \
    -X POST "$EP" \
    -H "Content-Type: application/json" \
    -d "$BODY" || true)
check "不带 token" "$code" "401"

echo "== 3) 错 token → 期望 401 =="
code=$(curl -sS -o /dev/null -w "%{http_code}" \
    -X POST "$EP" \
    -H "Authorization: Bearer wrong-token" \
    -H "Content-Type: application/json" \
    -d "$BODY" || true)
check "错 token" "$code" "401"

echo
echo "结果: $ok 通过, $fail 失败"
[[ $fail -eq 0 ]] && exit 0 || exit 1

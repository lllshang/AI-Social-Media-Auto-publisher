# API 手动测试清单

Base URL: `http://127.0.0.1:8765`

## 1. 登录

```bash
curl -s -X POST "$BASE/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```

## 2. 创建平台账号

```bash
curl -s -X POST "$BASE/api/platform-accounts" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"platform":"xhs","account_name":"test1"}'
```

## 3. 扫码登录（需 Chrome，headed 模式）

```bash
curl -s -X POST "$BASE/api/platform-accounts/1/login" \
  -H "Authorization: Bearer $TOKEN"
```

## 4. 检测 Cookie

```bash
curl -s -X POST "$BASE/api/platform-accounts/1/check-cookie" \
  -H "Authorization: Bearer $TOKEN"
```

## 5. AI 文案

```bash
curl -s -X POST "$BASE/api/ai/text/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"topic":"春茶上新","platform":"xhs"}'
```

## 6. AI 文生图（自动入库 materials）

```bash
curl -s -X POST "$BASE/api/ai/image/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"topic":"春茶封面","platform":"xhs","ratio":"3:4","count":1}'
```

## 7. 创建并执行发布任务

```bash
curl -s -X POST "$BASE/api/publish-tasks" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "title":"春茶上新",
    "content":"正文内容",
    "tags":["春茶","上新"],
    "platform":"xhs",
    "account_id":1,
    "content_type":"note",
    "material_ids":[1],
    "submit": true
  }'

curl -s -X POST "$BASE/api/publish-tasks/1/execute" \
  -H "Authorization: Bearer $TOKEN"

curl -s "$BASE/api/publish-tasks/1/logs" \
  -H "Authorization: Bearer $TOKEN"
```

## 8. Adapter 切换验证

修改环境变量后重启：

- `AI_TEXT_PROVIDER=stub` — 文案走 stub 实现
- `STORAGE=stub` — 存储走 stub 实现

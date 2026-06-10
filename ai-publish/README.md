# AI 多平台内容自动发布系统 — MVP

基于 OpenSpec change `mvp-xhs-auto-publish`（已归档）的首版后端实现。

## 文档索引

| 文档 | 说明 |
|------|------|
| [**项目总览（结构 + 全文档地图）**](../docs/project-overview.md) | **新人首选：代码结构、脚本、配置、路线图** |
| [部署指南（Mac / Windows / Linux / 腾讯云）](../docs/deployment.md) | **上服务器、Docker、腾讯云一键部署** |
| [日常使用手册](../docs/daily-usage.md) | 登录、发布、AI 配置 |
| [API 手动测试](../docs/api-test.md) | curl 接口清单 |
| [多平台扩展路线图](../docs/multi-platform-roadmap.md) | 抖音等平台规划 |

## 目录结构

```
ai-publish/                 # 应用代码
ai-publish/web/             # Vue 管理后台
ai-publish/start.sh         # macOS / Linux 本地启动
ai-publish/start.ps1        # Windows 本地启动
ai-publish/docker-compose.yml
vendor/social-auto-upload/  # 小红书 Playwright 参考项目
docs/deployment.md          # 部署文档
openspec/specs/             # 主规格
```

## 快速启动

### macOS / Linux（本地开发）

```bash
cd ai-publish
cp .env.example .env
./web.sh
./start.sh
```

### Windows（本地开发）

```powershell
cd ai-publish
copy .env.example .env
cd web; npm install; npm run build; cd ..
.\start.ps1
```

### Docker（Mac / Windows / Linux 服务器）

```bash
cd ai-publish
cp .env.docker.example .env
./web.sh
docker compose up -d --build
```

国内网络若拉取镜像超时，见部署文档 [4.1.1 国内镜像加速](../docs/deployment.md#411-国内网络docker-镜像加速)。

**腾讯云 / 生产服务器**：见 [4.5 一键部署](../docs/deployment.md#45-腾讯云轻量服务器--一键部署推荐客户交付)；发版升级见 [4.5.15 版本升级](../docs/deployment.md#4515-版本升级非首次部署)（`sync-to-server.sh` + `upgrade.sh`）。

- 本地开发：http://127.0.0.1:8765/app/
- Docker：http://127.0.0.1:8000/app/
- 默认账号：`admin` / `admin123`

## 验收状态

| 项 | 状态 |
|----|------|
| 小红书 API 端到端发布 | ✅ |
| Vue 管理后台 | ✅ |
| AI 模型自动检测 + 前台配 Key | ✅ |
| 三平台部署文档 | ✅ [deployment.md](../docs/deployment.md) |
| Docker Compose | ✅ 见 [deployment.md](../docs/deployment.md) |

# 阶段 D 试运行指南（无本机 Worker）

> 适用：已部署 **D.2 敏感词** + **D.3 发布限频**，**未**部署 D.4 本机 Worker。  
> 目的：用真实发布数据判断服务器端风控是否足够，再决定要不要上 D.4。

---

## 1. 推荐初始配置

| 配置项 | 建议值 | 说明 |
|--------|--------|------|
| `require_content_review` | `true` | 人审 + 机审双闸门 |
| `sensitive_word_enabled` | `true` | 先维护一小批行业敏感词 |
| `sensitive_word_action` | `block` | 命中即拦截 |
| `rate_limit_enabled` | `true` | |
| `rate_limit_min_interval_seconds` | `300` | 同账号 5 分钟间隔 |
| `rate_limit_daily_per_account` | `5`～`10` | 试运行期偏保守 |
| `rate_limit_max_concurrent` | `1` | 全局串行发布 |
| `rate_limit_include_retry` | `true` | 重试计入日上限 |
| `image_moderation_enabled` | `false` | D.5 未上时可关 |

---

## 2. 观测周期

建议 **连续 2～4 周**，每周填一次记录表。

### 每周记录表

| 项目 | 第 1 周 | 第 2 周 | 第 3 周 | 第 4 周 |
|------|---------|---------|---------|---------|
| 发布执行总次数 | | | | |
| 成功次数 | | | | |
| 失败次数 | | | | |
| 失败率（%） | | | | |
| 敏感词拦截次数 | | | | |
| 限频拦截次数 | | | | |
| 疑似平台风控失败次数* | | | | |
| 新增 expired 账号数 | | | | |
| 备注（DOM/素材/Cookie 等） | | | | |

\* 失败信息含「频繁」「违规」「限制」「风控」「封禁」等关键词，或运营人工判定。

数据来源：

- 工作台风控统计（D.O 交付后）
- `发布任务` 列表筛选 `failed`
- `平台账号` 健康状态

---

## 3. 何时考虑启动 D.4（本机 Worker）

满足 **任一** 可考虑单独立项 D.4：

1. 在限频已开启、发布量不高的情况下，**疑似风控失败**仍连续两周占比 > 10%
2. 多账号在 **同一服务器 IP** 下短期内集中 `expired` / 登录失效，而本机 Chrome 手动发布正常
3. 合规/内控明确要求：**发布动作必须在运营人员本机浏览器完成**

---

## 4. 何时可维持现状（不做 D.4）

- 失败主要来自 Cookie 过期、页面改版、素材格式等非风控因素，且可修复
- 限频后失败率 < 5%，账号状态稳定
- 发布频次低（如每账号每天 1～3 条），无批量诉求

---

## 5. 与现有部署的关系

| 环境 | 执行方式 | 试运行注意 |
|------|----------|------------|
| Docker 服务器 | 无头 Chromium | 关注 IP、频次；参考 `deployment.md` |
| 本地开发 | 可弹 Chrome | 仅作调试，不作为生产结论 |
| B 站 | biliup CLI | 限频策略同样生效，错误类型单独记录 |

---

## 6. 相关文档

- 任务清单：[phase-d-server-risk/tasks.md](../openspec/changes/phase-d-server-risk/tasks.md)
- 设计说明：[phase-d-server-risk/design.md](../openspec/changes/phase-d-server-risk/design.md)
- 日常操作：[daily-usage.md](./daily-usage.md)
- 部署：[deployment.md](./deployment.md)

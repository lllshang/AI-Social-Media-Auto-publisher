# Material Management (Delta)

## ADDED Requirements

### Requirement: 素材中心 AI 生图入口

管理后台素材页 SHALL 提供「AI 生成图片」入口，调用 `POST /api/materials/generate-image` 并将结果展示在列表中。

#### Scenario: 素材页生成图片

- **WHEN** 用户在素材页填写主题并点击生成
- **THEN** 系统调用文生图 API，新素材出现在列表且 `source=ai_generated`

### Requirement: 素材与草稿任务关联展示

任务详情与素材列表 MUST 能够展示素材与发布任务的关联关系。

#### Scenario: 任务详情展示素材

- **WHEN** 用户查看发布任务详情且任务含 `material_ids`
- **THEN** API 返回关联素材的 id、name、url、type 摘要信息

#### Scenario: 素材列表标记关联任务

- **WHEN** 某素材被至少一个发布任务引用
- **THEN** 素材列表 API MAY 返回 `used_by_task_ids` 字段供前端展示（可选实现）

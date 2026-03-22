# Skills

仓库包含两个 OpenClaw skill：

## `health-archive-manager`

写入侧 skill，负责初始化档案、归档文件、成员匹配、质量拒绝和重复拦截。

入口：

- `skills/health-archive-manager/SKILL.md`

## `health-archive-assistant`

读取侧 skill，负责查询档案、生成分析结果、总结和图表数据。

入口：

- `skills/health-archive-assistant/SKILL.md`

## 安装顺序

1. 先安装 `health-archive-manager`
2. 再安装 `health-archive-assistant`

两个 skill 可以分别安装，但推荐同时安装。

- 只安装 `health-archive-manager`：可以建档和归档
- 只安装 `health-archive-assistant`：如果本地档案尚未初始化，应提示补装 `health-archive-manager`

# Skills

这个仓库目前包含两个 OpenClaw skill：

## 1. `health-archive-manager`

写入侧 skill。

适用场景：

- 初始化本地健康档案目录
- 创建成员档案
- 医疗文件归档
- 质量拒绝
- 重复拦截

入口文件：

- `skills/health-archive-manager/SKILL.md`

## 2. `health-archive-assistant`

读取侧 skill。

适用场景：

- 查询某位成员的健康档案
- 提取分析 JSON
- 整理病史上下文
- 生成总结层结果
- 生成图表 spec / HTML

入口文件：

- `skills/health-archive-assistant/SKILL.md`

## 安装建议

推荐顺序：

1. 先安装 `health-archive-manager`
2. 再安装 `health-archive-assistant`

原因：

- 两个 skill 共享同一个本地数据目录
- `health-archive-manager` 负责初始化本地档案
- `health-archive-assistant` 默认读取已经存在的档案

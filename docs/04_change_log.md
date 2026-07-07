# 变更记录

## 2026-07-07

### 项目初始化
- 创建项目目录结构（src/tests/docs）
- 编写 CLAUDE.md 项目说明
- 编写 README.md
- 创建 .gitignore

### 文档
- `docs/00_project_brief.md` — 项目说明
- `docs/01_requirements.md` — 需求文档（三阶段目标）
- `docs/02_architecture.md` — 架构设计（待填充）
- `docs/03_task_plan.md` — 任务拆解
- `docs/04_change_log.md` — 变更记录
- `docs/05_data_format.md` — 数据格式说明（基于参考代码推断）
- `docs/06_api_usage.md` — 外部 API 调用方式（基于 classify_inference_errors_vllm.py）
- `docs/decisions/ADR-0001-tech-stack.md` — 技术栈选择（待填充）

### 全局统计模块
- 新建 `src/global_statistics/node_field_stats.py`
  - 统计每张图的 nodes 数量
  - 统计每个 node 的 id/device/topologyNode/configs 字段存在性
  - 按 split 汇总全局覆盖率
  - 输出 JSON 结果 + 终端可视化摘要
  - 新增 `--split` 参数：train（仅训练集）、val（仅验证集）、all（全部，默认）
- 新建 `src/global_statistics/node_subkey_stats.py`
  - 统计 device 内各顶层 key 的出现次数和覆盖率
  - 统计 topologyNode 内各顶层 key 的出现次数和覆盖率
  - 统计 configs[] 内各配置类型 key 的出现次数和覆盖率
  - 输出 JSON 结果 + 终端分类柱状图
  - 支持 `--split` 参数

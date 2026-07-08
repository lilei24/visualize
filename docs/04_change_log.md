# 变更记录

## 2026-07-07

### 项目初始化
- 创建项目目录结构（src/tests/docs）
- 编写 CLAUDE.md 项目说明
- 编写 README.md
- 创建 .gitignore

### 文档
- `docs/00_project_brief.md` — 项目说明
- `docs/00_project_brief.md` — 项目说明（含目录结构总览）
- `docs/01_requirements.md` — 需求文档（三阶段目标 + 全局统计摘要）
- `docs/02_architecture.md` — 架构设计（统计层 + 可视化层规划）
- `docs/03_task_plan.md` — 任务拆解
- `docs/04_change_log.md` — 变更记录
- `docs/05_data_format.md` — 数据格式说明（基于参考代码推断）
- `docs/06_api_usage.md` — 外部 API 调用方式（基于 classify_inference_errors_vllm.py）
- `docs/decisions/ADR-0001-tech-stack.md` — 技术栈选择（待填充）
- `CLAUDE.md` — 更新目录结构

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
- 新建 `src/global_statistics/node_value_distribution.py`
  - 统计 device.TYPE 的类别及占比
  - 统计 device.NET_ENVIRONMENT 的类别及占比
  - 统计 topologyNode.NODECLASS/DEVICEROLE/CLASSNAME 的类别及占比
  - 输出 JSON 结果 + 终端分类柱状图
  - 支持 `--split` 参数
- 新建 `src/global_statistics/edge_type_pair_stats.py`
  - 通过 links 统计边两端的 device.TYPE 配对
  - 无向图按字典序合并 A-B 和 B-A
  - 统计每种 TYPE 配对的边数量和占比
  - 输出 JSON 结果 + 终端分布图
  - 支持 `--split` 参数
- 新建 `src/global_statistics/type_configs_stats.py`
  - 按 device.TYPE 分组统计 configs 配置类型分布
  - 每种 TYPE 下列出各配置 key 的出现次数和占比
  - 全局汇总按配置总数降序排列
  - 输出 JSON 结果 + 终端分组柱状图
  - 支持 `--split` 参数
- 新建 `src/global_statistics/type_role_joint_stats.py`
  - 统计 device.TYPE × topologyNode.DEVICEROLE 联合分布
  - 按 TYPE 行 × DEVICEROLE 列展示交叉分布
  - 同时按 DEVICEROLE 汇总各 TYPE 占比
  - 输出 JSON 结果 + 终端交叉表
  - 支持 `--split` 参数
- 新建 `src/global_statistics/type_subtype_joint_stats.py`
  - 统计 device.TYPE × device.SUBTYPE 联合分布
  - 按 TYPE 行 × SUBTYPE 列展示交叉分布
  - 同时按 SUBTYPE 汇总各 TYPE 占比
  - 输出 JSON 结果 + 终端交叉表
  - 支持 `--split` 参数
  - SUBTYPE 缺失时标记为 `<无>`，值为空时标记为 `(空)`
- 新建 `src/global_statistics/link_field_stats.py`
  - 统计 links[].link 内 LEFTPORT/RIGHTPORT/CLASSNAME 的覆盖率
  - 统计各字段的值类别分布
  - 输出 JSON 结果 + 终端覆盖率柱状图 + 值分布
  - 支持 `--split` 参数
- 新建 `src/global_statistics/dg_type_overlap_stats.py`
  - 按图统计 DEVICEGROUPTYPES vs node TYPE 的三分类
  - 1) 完全对应（DG == Node）2) DG有Node无 3) Node有DG无
  - DEVICEGROUPTYPES 逗号分隔值自动拆分
  - 统计单位为图数量，后两类可重叠
  - 支持 `--split` 参数
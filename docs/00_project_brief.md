# 项目说明

## 项目概述

本项目是一个网络拓扑配置数据的可视化与分析工具，目标是：
1. 通过全局统计分析理解数据的分布和规律
2. 通过单图拓扑可视化深入了解配置与拓扑的关联
3. 最终挖掘有价值的配置预测下游任务

## 数据来源

数据为网络拓扑图 JSON 文件（几百张），每张图描述一个 AP 无线网络的完整配置。核心数据结构：

- `nodes[]` — 设备节点（含 `device`、`topologyNode`、`configs`）
- `links[]` — 节点间拓扑连线
- `deviceGroups[]` — 设备组级别配置

## 当前状态

### 已完成
- 数据格式分析（`docs/05_data_format.md`）
- 外部 API 调用方式总结（`docs/06_api_usage.md`）
- 全局统计脚本 5 个（`src/global_statistics/`）

### 进行中
- 阶段一：单图拓扑可视化（需求设计完成）

### 规划中
- 阶段二：跨图统计分析
- 阶段三：预测任务挖掘

## 目录结构

```
project/
├── docs/                          # 项目文档
│   ├── 00_project_brief.md        # 项目说明
│   ├── 01_requirements.md         # 需求文档
│   ├── 02_architecture.md         # 架构设计
│   ├── 03_task_plan.md            # 任务拆解
│   ├── 04_change_log.md           # 变更记录
│   ├── 05_data_format.md          # 数据格式定义
│   ├── 06_api_usage.md            # 外部 API 调用方式
│   └── decisions/
│       └── ADR-0001-tech-stack.md # 架构决策记录
├── src/
│   └── global_statistics/         # 全局统计脚本
│       ├── node_field_stats.py    # node 顶层字段存在性
│       ├── node_subkey_stats.py   # 子 key 分布与覆盖率
│       ├── node_value_distribution.py  # 关键字段值分布
│       ├── edge_type_pair_stats.py     # 边 TYPE 配对统计
│       └── type_configs_stats.py       # 按 TYPE 的 configs 分布
├── 参考代码/                      # 数据处理参考脚本
│   ├── build_config_generation_dataset.py
│   └── classify_inference_errors_vllm.py
├── tests/
├── README.md
├── CLAUDE.md
└── .gitignore
```

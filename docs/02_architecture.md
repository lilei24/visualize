# 架构设计

## 当前架构

项目目前处于**数据分析阶段**，架构分为两层：

### 1. 统计层（`src/global_statistics/`）

批量读取数据集 JSON，输出统计 JSON 和终端摘要。

```
datasets/{train,val}/*.json
        │
        ▼
┌─────────────────────────────────┐
│      统计脚本（5 个独立脚本）        │
│                                 │
│  node_field_stats.py            │  节点字段存在性
│  node_subkey_stats.py           │  子 key 覆盖率
│  node_value_distribution.py     │  关键字段值分布
│  edge_type_pair_stats.py        │  边 TYPE 配对
│  type_configs_stats.py          │  按 TYPE 的 configs 分布
└─────────────────────────────────┘
        │
        ▼
statistics/*.json
```

每个脚本：
- 接受 `dataset_root`（数据集路径）+ `--split`（train/val/all）
- 递归扫描 `dataset_root/{split}/**/*.json`
- 提取指定维度的统计数据
- 输出 `statistics/*.json`（summary + per_file）+ 终端柱状图

### 2. 可视化层（规划中）

后续阶段一将构建交互式 Web 前端：

```
浏览器 ←→ Python 后端 ←→ datasets/*.json
  │
  ├── 拓扑图渲染（力导向布局）
  ├── 节点详情面板（device + topologyNode + configs）
  └── 配置树形展开
```

## 数据流

```
数据集 JSON  →  统计脚本  →  statistics/*.json  →  (未来) 可视化仪表盘
     │
     └──→  (未来) 单图加载器  →  前端拓扑渲染
```

## 技术选型

| 层 | 技术 | 说明 |
|------|------|------|
| 统计脚本 | Python 标准库 + json | 无外部依赖，可直接在服务器运行 |
| 后续前端 | 待定 | 阶段一技术选型时将记录 ADR |

## 设计原则

- **无外部依赖**：统计脚本仅依赖 Python 标准库，可直接拷贝到服务器运行
- **命令行驱动**：所有脚本使用 argparse，支持 `--split` 过滤
- **输出双格式**：JSON（程序消费）+ 终端柱状图（人类阅读）
- **容错优先**：字段缺失、JSON 解析失败均记录 issue 而非崩溃

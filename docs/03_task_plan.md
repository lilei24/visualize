# 任务拆解

## 已完成

### 1. 项目初始化
- [x] 项目目录结构搭建
- [x] CLAUDE.md 配置
- [x] 数据格式文档 (05_data_format.md)
- [x] API 调用方式文档 (06_api_usage.md)

### 2. 全局统计 — node 字段统计
- [x] `src/global_statistics/node_field_stats.py`
  - 统计每张图的 nodes 数量
  - 统计每个 node 的 id / device / topologyNode / configs 字段存在性
  - 按 split 汇总覆盖率
  - 输出 JSON 结果和终端摘要

### 3. 全局统计 — node 子 key 统计
- [x] `src/global_statistics/node_subkey_stats.py`
  - 统计 device 内各顶层 key 的分布和覆盖率
  - 统计 topologyNode 内各顶层 key 的分布和覆盖率
  - 统计 configs[] 内各配置类型 key 的分布和覆盖率
  - 按 split 汇总，按频次降序排列

### 4. 全局统计 — node 值分布统计
- [x] `src/global_statistics/node_value_distribution.py`
  - 统计 device.TYPE 的类别及占比
  - 统计 device.NET_ENVIRONMENT 的类别及占比
  - 统计 topologyNode.NODECLASS 的类别及占比
  - 统计 topologyNode.DEVICEROLE 的类别及占比
  - 统计 topologyNode.CLASSNAME 的类别及占比

### 5. 全局统计 — 边 TYPE 配对统计
- [x] `src/global_statistics/edge_type_pair_stats.py`
  - 通过 links 提取每条边的 source/target 节点
  - 按 (node1.device.TYPE, node2.device.TYPE) 配对统计边数量
  - 无向图按字典序排序，A-B 和 B-A 合并
  - 统计每种 TYPE 配对的边数量和占比

## 待完成

### 7. 阶段一：单图拓扑可视化
- [ ] 拓扑视图渲染（力导向图）
- [ ] 节点详情面板（devices + topologyNode + configs）
- [ ] configs 可折叠树形展示
- [ ] deviceGroups 展示
- [ ] 图切换器

### 8. 阶段二：跨图统计分析
- [ ] 待细化

### 9. 阶段三：预测任务挖掘
- [ ] 待细化

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

### 6. 全局统计 — 按 TYPE 的 configs 配置分布
- [x] `src/global_statistics/type_configs_stats.py`
  - 将 nodes 按 device.TYPE 分组
  - 统计每种 TYPE 下 configs[] 中各配置 key 的出现次数和占比
  - 按 split 汇总，按配置总数降序排列

### 7. 全局统计 — TYPE × DEVICEROLE 联合分布
- [x] `src/global_statistics/type_role_joint_stats.py`
  - 统计 (device.TYPE, topologyNode.DEVICEROLE) 组合的节点数
  - 按 TYPE 行 × DEVICEROLE 列展示交叉分布
  - 同时按 DEVICEROLE 汇总各 TYPE 分布
  - 支持 `--split` 参数

### 8. 全局统计 — TYPE × SUBTYPE 联合分布
- [x] `src/global_statistics/type_subtype_joint_stats.py`
  - 统计 (device.TYPE, device.SUBTYPE) 组合的节点数
  - 按 TYPE 行 × SUBTYPE 列展示交叉分布
  - 同时按 SUBTYPE 汇总各 TYPE 分布
  - 支持 `--split` 参数

### 9. 全局统计 — link 字段统计
- [x] `src/global_statistics/link_field_stats.py`
  - 统计 links[].link 内 LEFTPORT/RIGHTPORT/CLASSNAME 的覆盖率
  - 统计各字段的值类别分布
  - 支持 `--split` 参数

## 待完成

### 10. 阶段一：单图拓扑可视化
- [ ] 拓扑视图渲染（力导向图）
- [ ] 节点详情面板（devices + topologyNode + configs）
- [ ] configs 可折叠树形展示
- [ ] deviceGroups 展示
- [ ] 图切换器

### 11. 阶段二：跨图统计分析
- [ ] 待细化

### 12. 阶段三：预测任务挖掘
- [ ] 待细化

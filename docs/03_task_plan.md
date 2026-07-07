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

## 待完成

### 3. 阶段一：单图拓扑可视化
- [ ] 拓扑视图渲染（力导向图）
- [ ] 节点详情面板（devices + topologyNode + configs）
- [ ] configs 可折叠树形展示
- [ ] deviceGroups 展示
- [ ] 图切换器

### 4. 阶段二：跨图统计分析
- [ ] 待细化

### 5. 阶段三：预测任务挖掘
- [ ] 待细化

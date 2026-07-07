# 数据格式说明

> 推断自 `参考代码/build_config_generation_dataset.py`。

## 原始数据：网络图 JSON

每个 JSON 文件描述一张网络拓扑图，顶层为 dict 对象。

### 顶层字段

顶层字段不固定，常见的有：

| 字段           | 类型          | 必填 | 说明                 |
| ------------ | ----------- | -- | ------------------ |
| directed     | bool        | 是  | 有向/无向图             |
| multigraph   | bool        | 是  | 是否多重图              |
| nodes        | list\[dict] | 否  | 网络节点列表，图中无节点时可能不存在 |
| deviceGroups | list\[dict] | 是  | 设备组列表              |
| links        | list\[dict] | 否  | 拓扑连线列表             |

其中 **nodes** 和 **deviceGroups** 是核心数据，携带配置信息。

***

### nodes\[] — 节点对象

每个节点代表一个网络设备。内部字段不固定，常见的有：

| 字段           | 类型          | 说明                                     |
| ------------ | ----------- | -------------------------------------- |
| id           | string      | 节点唯一标识，被 links 的 source/target 引用      |
| device       | dict        | 设备物理属性（NAME/MANUFACTURER/MODEL/TYPE 等） |
| topologyNode | dict        | 拓扑角色（NODECLASS/DEVICEROLE/CLASSNAME）   |
| configs      | list\[dict] | **核心**：节点级配置列表                         |

### deviceGroups\[] — 设备组对象

设备组描述跨节点共享的配置。内部字段不固定，常见的有：

| 字段          | 类型          | 说明                              |
| ----------- | ----------- | ------------------------------- |
| deviceGroup | dict        | 设备组元信息（NAME/DEVICEGROUPTYPES 等） |
| configs     | list\[dict] | **核心**：设备组级别配置列表                |

***

### configs\[] — 配置对象（核心）

`configs` 是 nodes 和 deviceGroups 中最重要的字段。它是一个列表，其中每个元素是一个配置对象：

- 每个配置对象以**一个顶层字符串 key** 作为配置类型名，值为该配置的参数（任意嵌套 JSON）。
- **配置 key 不固定**：不同图、不同节点的配置类型和数量可任意变化。
- 一个配置对象通常只包含一个顶层 key。

示例中出现的配置类型（仅举例，实际不限于此）：

| 配置 key                      | 示例值                                                   |
| --------------------------- | ----------------------------------------------------- |
| cloud-ap-interfaces         | `{ "cloud-ap-interface": [{ "enable": true, ... }] }` |
| ap-psk                      | `{ "tunnel-encrypt": true }`                          |
| zone-info                   | `{ "zone-sn": "" }`                                   |
| apstormsuppression-business | `{ "arp": true }`                                     |

***

### links\[] — 拓扑连线

描述节点间的连接关系：

| 字段     | 类型     | 说明                                       |
| ------ | ------ | ---------------------------------------- |
| source | string | 源节点 id                                   |
| target | string | 目标节点 id                                  |
| link   | dict   | 链路属性（LEFTPORT/RIGHTPORT/LABEL/CLASSNAME） |

***

## 完整示例

```json
{
    "directed": false,
    "multigraph": false,
    "deviceGroups": [
        {
            "deviceGroup": {
                "NAME": "",
                "DEVICEGROUPTYPES": "AP"
            },
            "configs": [
                {
                    "ap-psk": {
                        "tunnel-encrypt": true
                    }
                },
                {
                    "zone-info": {
                        "zone-sn": ""
                    }
                },
                {
                    "apstormsuppression-business": {
                        "arp": true
                    }
                }
            ]
        }
    ],
    "nodes": [
        {
            "id": "",
            "device": {
                "NAME": "",
                "MANUFACTURER": "",
                "MODEL": "",
                "TYPE": "",
                "SOFTWARE_VERSION": "",
                "NET_ENVIRONMENT": 0,
                "APTYPE": "",
                "SUBTYPE": ""
            },
            "topologyNode": {
                "NODECLASS": "",
                "DEVICEROLE": "",
                "CLASSNAME": ""
            },
            "configs": [
                {
                    "cloud-ap-interfaces": {
                        "cloud-ap-interface": [
                            {
                                "enable": true,
                                "sence": "root",
                                "macLimit": false,
                                "admin-status": true,
                                "connect-to-ac-sign": true
                            }
                        ]
                    }
                }
            ]
        }
    ],
    "links": [
        {
            "source": "",
            "target": "",
            "link": {
                "LEFTPORT": "",
                "RIGHTPORT": "",
                "LABEL": "",
                "CLASSNAME": ""
            }
        }
    ]
}
```

## 数据集目录约定

```
datasets/
├── train/
│   ├── topology_001.json
│   ├── topology_002.json
│   └── ...
└── val/
    ├── topology_101.json
    └── ...
```

## 关键特征总结

1. **字段不固定**：顶层和子层字段均可能缺失或变化，需以存在性判断代替硬编码 schema。
2. **configs 是核心可变部分**：配置 key 和值结构完全由数据驱动，没有固定枚举。
3. **图结构**：nodes + links 构成网络拓扑，deviceGroups 提供跨节点的共享配置层。
4. **数据按 split 拆分**：train/val 目录各自独立。


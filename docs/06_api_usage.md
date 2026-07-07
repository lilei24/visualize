# 外部 API 调用方式

> 总结自 `参考代码/classify_inference_errors_vllm.py`。

## 概述

本项目通过 **OpenAI 兼容的 HTTP API** 调用本地部署的 vLLM 推理服务。Python 侧使用 `openai` 官方 SDK，与服务端解耦。

## 客户端初始化

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",  # vLLM 服务地址
    api_key="empty"                       # vLLM 默认不需要认证
)
```

| 参数 | 说明 |
| --- | --- |
| base_url | vLLM OpenAI 兼容端点，路径必须以 `/v1` 结尾 |
| api_key | vLLM 本地部署通常不需要真实 key，传占位字符串即可 |

> 依赖安装：`pip install openai`

---

## 调用方式

### 基本 Chat Completions 调用

```python
completion = client.chat.completions.create(
    model="qwen3-8b",                              # 模型名称
    messages=[{"role": "user", "content": prompt}], # 标准 messages 格式
    temperature=0.0,                                # 温度参数
    max_tokens=512,                                 # 最大输出 token 数
)
```

### 获取响应文本

```python
raw_output = completion.choices[0].message.content
```

### 完整调用参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| model | str | 模型名称，需与 vLLM 服务端注册名称一致 |
| messages | list[dict] | 标准 OpenAI messages 格式，`role` + `content` |
| temperature | float | 采样温度，分类任务建议 0.0 |
| max_tokens | int | 输出 token 上限 |
| extra_body | dict | 透传给 vLLM 的额外参数（OpenAI SDK 不支持的字段放这里） |

---

## 服务端特有参数（extra_body）

OpenAI SDK 不直接支持某些 vLLM/模型特有参数，通过 `extra_body` 透传：

```python
# 禁用 Qwen 模型的 thinking 模式
kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
```

`extra_body` 中的字段会被原样合并到请求体里发送给服务端。

---

## 结构化输出（Prompt Engineering 方式）

脚本没有使用 `response_format` 参数，而是通过 **prompt 约束模型输出 JSON**：

```
必须返回一个 JSON 对象，不要 Markdown，不要解释文本。格式：
{
  "error_category": "五类之一，必须原样输出类别名",
  "error_reason": "简洁说明判断依据",
  "sub_reason": "可选"
}
```

解析时对响应做**防御性处理**：

```python
# 1. 去除 markdown 代码围栏
cleaned = re.sub(r"^```(?:json)?\s*(.*?)\s*```$", ..., text)

# 2. 尝试直接解析 JSON
parsed = json.loads(cleaned)

# 3. 失败则从文本中提取第一个 {...} 再解析
match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
parsed = json.loads(match.group(0))

# 4. 校验必要字段，fallback 到默认值
```

---

## 完整调用流程

```
┌─────────────┐     HTTP POST /v1/chat/completions     ┌──────────────┐
│  Python      │ ──────────────────────────────────────> │  vLLM Server  │
│  openai SDK  │ <────────────────────────────────────── │  :8000        │
└─────────────┘     JSON response                       └──────────────┘

请求体示例：
{
    "model": "qwen3-8b",
    "messages": [{"role": "user", "content": "..."}],
    "temperature": 0.0,
    "max_tokens": 512,
    "chat_template_kwargs": {"enable_thinking": false}
}

响应体示例（OpenAI 格式）：
{
    "choices": [{
        "message": {
            "role": "assistant",
            "content": "{\"error_category\": \"2.2 ...\"}"
        }
    }]
}
```

## 关键约定

1. **base_url 以 `/v1` 结尾**，SDK 会自动拼接 `/chat/completions`。
2. **api_key 可传任意字符串**，本地 vLLM 不做校验。
3. **temperature 设 0.0**，分类/结构化提取任务要求确定性输出。
4. **extra_body 是扩展入口**，所有非 OpenAI 标准参数都通过它透传。
5. **模型输出不可信**，JSON 解析必须带 fallback 和校验逻辑。

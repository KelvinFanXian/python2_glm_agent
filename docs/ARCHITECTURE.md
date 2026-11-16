# 代码结构

项目按职责拆成五个模块，全部使用 Python 2.7 标准库。

为兼容旧 iMac，网络连接使用 Python 2.7 的 `urllib2` 同步 API；文件与命令操作使用同代标准库。服务端协议仍是 GLM 的 Chat Completions HTTP 接口，客户端使用旧版标准库并不意味着调用已停用的 GLM 服务端接口。

| 文件 | 职责 |
| --- | --- |
| `agent.py` | 命令行参数、终端输入输出、`/save` 和用户确认；启动各组件。 |
| `glm_config.py` | 读取绝对路径 key 文件、Hermes `.env` 与环境变量；确定模型名和 API 地址。 |
| `glm_client.py` | 把消息和工具定义发给 GLM Chat Completions 接口，解析响应并处理 HTTP 错误。 |
| `agent_core.py` | 系统提示词、`/code` 提示词、工具调用循环和代码块提取。 |
| `project_tools.py` | 六个本地工具的定义与执行、工作目录边界、文件和命令的限制。 |

一次用户输入的流程：

```text
终端输入 → agent.py → agent_core.py → glm_client.py → GLM
                         ↑                  ↓
                         └─ project_tools.py ← 工具调用
```

`glm_config.load_config()` 在启动时生成 `GlmConfig`。`agent.py` 将配置和 `project_tools.py` 的工具定义传给 `GlmClient`；HTTP 连接模块无需导入本地工具实现。`agent_core.agent_turn()` 只依赖客户端的 `chat(messages)` 方法和项目工具的 `call(name, arguments)` 方法，因此离线测试可以替换客户端，无需真实 key 或网络。

修改模型接入时优先编辑 `glm_config.py` 和 `glm_client.py`；修改工具时编辑 `project_tools.py`；修改交互策略时编辑 `agent_core.py`。对应的离线测试在 `tests/test_agent.py`。

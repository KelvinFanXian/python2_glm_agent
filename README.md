# Python 2 GLM Agent

为旧款 Mac 准备的命令行聊天与代码生成工具。只使用 Python 2.7 标准库，不需要 pip 安装依赖。

**旧机器兼容是本项目的首要约束。** 客户端刻意使用 Python 2.7 时代已有的标准库 API，例如 `urllib2.Request` / `urllib2.urlopen`、`json`、`io` 和 `subprocess`。代码不依赖新版 GLM SDK、`asyncio`、类型注解或 f-string，因此可以在具备合适 Python 2.7 与 TLS 环境的旧 iMac 上运行。这里的“旧 API”指本机 Python 调用方式；连接 GLM 时仍需使用账户当前可用的 Chat Completions HTTP 地址。

当前支持连续聊天、查看和搜索项目文件、修改代码、运行命令，以及把生成的代码保存到本地。模型通过 GLM 的函数调用格式选择工具；文件工具限制在指定工作目录内。

## 运行

首次配置 GLM key，请按 [GLM API Key 配置指南](docs/GLM_KEY_SETUP.md) 操作。推荐把 key 单独存成一个本机文件，并通过绝对路径传给程序；也支持环境变量和 Hermes 的 `.env`。

在终端检查版本：

```sh
cd python2_glm_agent
python --version
```

需要 Python 2.7。把 Hermes 使用的同一个 GLM key 单独写入本机文件，然后传入**绝对路径**：

```sh
python2.7 agent.py --key-file /Users/你的用户名/.config/glm-agent/key \
  --workspace /path/to/your/project
```

key 文件只放一行纯 key，不写 `GLM_API_KEY=`。建议放在 Git 仓库外，并设置权限 `chmod 600 /Users/你的用户名/.config/glm-agent/key`。

如果 Hermes 已把 key 写在 `.env` 文件中，可直接指定该文件（支持 `GLM_API_KEY`、`ZAI_API_KEY`、`ZHIPUAI_API_KEY`、`HERMES_API_KEY`；当 `OPENAI_BASE_URL` 指向 GLM 时也支持 `OPENAI_API_KEY`）：

```sh
python agent.py --hermes-env /path/to/hermes/.env
```

默认还会查找 `~/.hermes/.env` 与 `~/.config/hermes/.env`。`--key-file` 优先于这些配置。程序不会修改 Hermes 的配置文件，也不会复制 key 到本项目。

`.env` 文件只支持简单的 `KEY=VALUE` 行、可选的 `export` 前缀和成对引号；程序不会执行其中的 shell 脚本。可参考 [`.env.example`](.env.example)。如果 Hermes 使用其他配置格式，请把 key 放进环境变量。

默认接口为 Coding Plan 的 `https://open.bigmodel.cn/api/coding/paas/v4/chat/completions`，默认模型为 `glm-5.3-flash`。使用前请确认你的 key 有 Coding Plan 权限。如果 Hermes 的 key 属于其他 GLM 接口，请使用其对应的地址和模型名：

```sh
python agent.py --api-url 'https://api.z.ai/api/paas/v4/chat/completions' --model glm-5.3-flash
```

如果 Hermes 使用 **GLM Coding Plan**，请使用 Hermes 中配置的 Coding Plan 地址，例如国内地址：

```sh
python agent.py --api-url 'https://open.bigmodel.cn/api/coding/paas/v4' --model glm-5.3-flash
```

也可设置 `GLM_API_URL` 和 `GLM_MODEL` 环境变量。GLM 地址可写到 `/v4` 或完整的 `/chat/completions`。命令行参数优先。key 必须与所选平台和接口匹配；实际可用模型取决于账户。接口请求格式可参考 [Z.AI 官方示例](https://docs.z.ai/guides/capabilities/mcp-call)。

模型代码 `glm-5.3-flash` 和 Coding Plan 可用性见 [Z.AI 模型文档](https://docs.z.ai/guides/vlm/glm-5.3-flash)；国内 Coding Plan 的专用地址可参考 [ZCode 配置文档](https://zcode.z.ai/cn/docs/configuration)。

## 使用

直接输入文字聊天或交代项目任务。常用命令：

```text
/code 用 Python 2.7 写一个批量重命名文件的脚本
/save rename.py
/clear
/quit
```

让 agent 操作项目的例子：

```text
> 看一下这个项目有哪些 Python 文件
> 找到登录逻辑，修复空密码时的报错
> 运行现有测试并总结结果
```

文件工具包括 `list_files`、`read_file`、`search_text`、`write_file` 和 `edit_file`。命令工具为 `run_command`，每次执行前会展示命令并询问；修改或覆盖已有文件也会询问。命令在工作目录中启动，但命令本身可以访问该目录之外的系统资源，确认前请看清内容。

`--workspace` 默认为启动时的当前目录。文件工具拒绝越界路径、符号链接跳出目录、`.git` 和常见密钥文件。读取、搜索和命令输出都有长度限制；单轮最多进行 8 次模型工具调用。

`/code` 生成一个完整代码块；`/save` 把最近一次生成的代码保存为 UTF-8 文件。覆盖已有文件前会询问。

| 命令 | 作用 |
| --- | --- |
| 普通文字 | 聊天，保留最近约 10 轮对话 |
| `/code 需求` | 生成一个源文件的代码 |
| `/save 路径` | 保存最近生成的代码；父目录需已存在 |
| `/clear` | 清空本次对话和待保存代码 |
| `/quit` 或 `/exit` | 退出 |

对话只保存在进程内存中，退出后不会持久化。生成和修改的代码由模型提供，请检查改动。`/save` 和项目工具的文件路径都相对于 `--workspace`。

## 旧 iMac 注意事项

兼容策略是尽量降低**客户端软件依赖**：Python 2.7 标准库直接发 HTTP 请求，不要求安装现代 SDK 或 Python 3。它不能替代服务端要求的 TLS 支持；即使代码使用旧版 Python API，机器上的 OpenSSL 和证书仍须能与 GLM 服务建立安全连接。

Python 2.7 自带的 `urllib2` 会使用该解释器链接的 OpenSSL。过旧的 macOS / Python 构建可能无法与 GLM 服务器协商当前要求的 TLS 协议，表现为 SSL 握手失败。此时需要在该机器上安装带较新 OpenSSL 的 Python 2.7，或让请求经由受信任的现代代理。程序不会主动关闭证书校验；但部分早期 Python 2.7 构建默认不验证 HTTPS 证书，建议使用 Python 2.7.9 或更高版本。

Python 2.7 已停止维护。请只在明确需要兼容旧系统的机器上使用，并保护好 API key。

具体检查步骤和错误处理见 [旧 iMac 安装与排错指南](docs/IMAC_SETUP.md)。2009 年 iMac 的实际兼容性取决于其 macOS、Python 和 OpenSSL 版本。

## 项目文件

模块分工和调用流程见 [代码结构说明](docs/ARCHITECTURE.md)。

```text
python2_glm_agent/
├── agent.py              # 命令行入口
├── glm_config.py         # key、模型和接口地址
├── glm_client.py         # GLM HTTP 连接
├── agent_core.py         # 对话与工具调用循环
├── project_tools.py      # 项目文件和命令工具
├── .env.example          # 不含真实密钥的配置示例
├── .gitignore            # 忽略本地密钥文件与日志
├── docs/ARCHITECTURE.md  # 模块分工和调用流程
├── docs/IMAC_SETUP.md    # 旧 iMac 安装与排错
├── docs/GLM_KEY_SETUP.md # GLM key 配置步骤
├── tests/test_agent.py   # 不联网的工具和接口格式测试
└── README.md
```

## 验证情况

在 Python 2.7 环境中可运行不联网测试：

```sh
python2.7 -m unittest discover -s tests
```

目前 15 项离线测试已在开发环境通过。该环境只有 Python 3，因此使用 `lib2to3` 转换源码后执行测试，同时检查 Python 2 语法。尚未在真实 Python 2.7 解释器、目标 iMac 或 Hermes 实际配置上完成连通测试。

分享到 GitHub 前请检查 `git status`，确认没有暂存真实 key、终端日志或个人配置文件。`.env.example` 只包含占位符。

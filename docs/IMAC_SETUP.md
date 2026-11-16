# 旧 iMac 安装与排错

本文针对 2009 年的 iMac。能否运行主要取决于机器上实际安装的 macOS、Python 和 OpenSSL，而不是 iMac 的年份。

## 1. 检查运行环境

打开“终端”，运行：

```sh
python --version
python -c 'import ssl; print ssl.OPENSSL_VERSION'
```

程序要求 Python 2.7。建议使用 Python 2.7.9 或更高版本，并确保它链接到支持当前 HTTPS/TLS 的 OpenSSL。`python --version` 如果显示 2.6 或 3.x，须使用机器上实际的 Python 2.7 命令启动，例如 `python2.7 agent.py`。安装新解释器时不要覆盖 macOS 自带的系统 Python。

## 2. 放置项目并配置密钥

把整个 `python2_glm_agent` 目录复制到 iMac。进入目录后，任选一种方式：

```sh
export GLM_API_KEY='你的 GLM key'
python agent.py
```

或直接使用 Hermes 的 `.env`：

```sh
python agent.py --hermes-env /path/to/hermes/.env
```

要让 agent 操作指定项目，请加上 `--workspace`：

```sh
python agent.py --hermes-env /path/to/hermes/.env --workspace /path/to/project
```

模型可以在该目录内列文件、读文件、搜索、写文件和修改文件。运行命令时程序会逐次请求确认；命令本身可能访问工作目录之外，确认前请审阅。

如果 Hermes 使用 Coding Plan，确保接口地址与它的配置相同，例如：

```sh
python agent.py --hermes-env /path/to/hermes/.env \
  --api-url 'https://open.bigmodel.cn/api/coding/paas/v4'
```

`--api-url` 可以是以 `/v4` 结尾的基础地址，也可以是完整的 `/chat/completions` 地址。

## 3. 常见问题

| 现象 | 检查方法 |
| --- | --- |
| `没有找到 GLM key` | 确认当前终端设置了 `GLM_API_KEY`，或 `--hermes-env` 指向可读的 `.env` 文件。`OPENAI_API_KEY` 只有在同一配置的 `OPENAI_BASE_URL` 指向 GLM HTTPS 地址时才会被使用。 |
| HTTP 401 / 403 | 检查 key 是否有效，以及它是否属于所选的国内、Z.AI 或 Coding Plan 接口。 |
| HTTP 404 / 模型错误 | 检查 `--api-url` 和 `--model`，并与 Hermes 的实际配置对照。 |
| SSL 握手或证书错误 | 检查 `ssl.OPENSSL_VERSION`、系统时间和证书。过旧的 Python/OpenSSL 可能不支持服务端所需 TLS；应更新 Python/OpenSSL 或使用受信任的现代代理。不要通过关闭证书校验来处理。 |
| 中文显示乱码 | 在终端尝试 `export LANG=zh_CN.UTF-8`，再启动程序。 |
| `/save` 失败 | 目标文件的父目录必须已经存在，当前用户也需要写入权限。 |
| 工具调用格式错误 | 检查所选模型和接口是否支持 Chat Completions 的 `tools` / `tool_calls` 函数调用格式。 |

## 4. 分享到 GitHub 前

项目的 `.gitignore` 会忽略本地 `.env` 文件。提交前仍应运行 `git status`，确认没有把真实 key、终端输出日志或个人配置文件加入暂存区。`.env.example` 仅保留占位符。

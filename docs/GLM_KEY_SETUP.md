# 配置 GLM API Key

本项目不会替你创建 GLM key。请使用你在 Hermes 中已经配置的同一个 key，并确保 API 地址与这个 key 所属的平台和套餐一致。**不要把真实 key 写进 `agent.py`、README 或提交到 GitHub。**

## 方法一：使用本机绝对路径的 key 文件（推荐）

在 iMac 上新建一个位于 Git 仓库之外的文件。例如先创建目录并用文本编辑器打开文件：

```sh
mkdir -p /Users/你的用户名/.config/glm-agent
nano /Users/你的用户名/.config/glm-agent/key
```

文件里**只写一行纯 key**，例如：

```text
你的真实GLMkey
```

不要写 `GLM_API_KEY=`，也不要添加第二行说明。把文件权限限制为当前用户可读写：

```sh
chmod 600 /Users/你的用户名/.config/glm-agent/key
```

启动时传这个文件的**绝对路径**：

```sh
cd /path/to/python2_glm_agent
python2.7 agent.py --key-file /Users/你的用户名/.config/glm-agent/key \
  --workspace /path/to/your/project
```

路径必须从 `/` 开始。程序只读取这个文件，不修改它，也不会把 key 打印到终端。指定 `--key-file` 后，它优先于环境变量和 `.env` 中的 key。API 地址和模型仍可通过 `--api-url`、`--model` 指定。

## 方法二：当前终端设置环境变量

在 Mac 终端中进入项目目录，运行：

```sh
cd /path/to/python2_glm_agent
export GLM_API_KEY='在这里填入你自己的 key'
python2.7 agent.py --workspace /path/to/your/project
```

这种方式只对当前终端会话生效。关闭终端后需要重新设置。命令中的 key 可能留在 shell 历史记录中；推荐使用方法一。

## 方法三：读取本地 `.env` 文件

在项目目录复制示例文件，编辑副本并填入真实 key：

```sh
cp .env.example .env
chmod 600 .env
python2.7 agent.py --hermes-env .env --workspace /path/to/your/project
```

`.env` 已被项目的 `.gitignore` 排除。示例内容如下：

```text
GLM_API_KEY=你的真实key
GLM_API_URL=https://open.bigmodel.cn/api/paas/v4
GLM_MODEL=glm-4.6
```

修改 `.env` 中的地址和模型时，以 Hermes 已经能正常使用的配置为准。程序不会自动读取项目目录里的 `.env`，因此启动时须显式传 `--hermes-env .env`。

## 方法四：直接复用 Hermes 的 `.env`

如果 Hermes 已有可读的 `.env`，无需复制 key：

```sh
python2.7 agent.py --hermes-env /path/to/hermes/.env \
  --workspace /path/to/your/project
```

不指定 `--hermes-env` 时，程序会尝试 `~/.hermes/.env` 和 `~/.config/hermes/.env`。如果 Hermes 的配置文件不在这些位置，或者不是简单的 `KEY=VALUE` 格式，请明确传路径，或用方法一设置环境变量。

程序识别 `GLM_API_KEY`、`ZAI_API_KEY`、`ZHIPUAI_API_KEY` 和 `HERMES_API_KEY`。如果 Hermes 使用 OpenAI 兼容变量 `OPENAI_API_KEY`，则同一配置中还要有指向 GLM HTTPS 域名的 `OPENAI_BASE_URL`。例如：

```text
OPENAI_API_KEY=你的真实key
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
```

## 选择正确的 API 地址

| key 类型 | `--api-url` 示例 |
| --- | --- |
| 智谱国内通用 API | `https://open.bigmodel.cn/api/paas/v4` |
| 智谱国内 Coding Plan | `https://open.bigmodel.cn/api/coding/paas/v4` |
| Z.AI 国际通用 API | `https://api.z.ai/api/paas/v4` |
| Z.AI 国际 Coding Plan | `https://api.z.ai/api/coding/paas/v4` |

例子：

```sh
python2.7 agent.py --hermes-env /path/to/hermes/.env \
  --api-url 'https://open.bigmodel.cn/api/coding/paas/v4' \
  --model glm-4.6 --workspace /path/to/your/project
```

地址可以只写到 `/v4`，程序会补上 `/chat/completions`。默认是智谱国内通用 API，模型默认是 `glm-4.6`。如果收到 HTTP 401、403 或模型错误，先核对 Hermes 中实际使用的 key、地址、模型和套餐。

## 提交到 GitHub 前检查

```sh
git status --short
git diff --cached --name-only
```

确认提交列表中只有 `.env.example`，没有 `.env`、原始 key 文件、Hermes 配置文件或包含真实 key 的日志。若曾把真实 key 提交到仓库，即使之后删除文件，也应立即在 GLM 平台撤销并重新生成该 key。

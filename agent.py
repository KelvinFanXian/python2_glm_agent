#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Small GLM chat and coding agent for Python 2.7."""
from __future__ import print_function

import argparse
import io
import json
import locale
import os
import re
import sys
import urllib2
from urlparse import urlparse
from project_tools import ProjectTools, SCHEMAS


DEFAULT_URL = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
SYSTEM_PROMPT = (u'你是一个实用的编程助手。回答要准确、简洁。'
                 u'需要了解或修改项目时，调用提供的工具；先读取相关文件，再修改。'
                 u'不要假称已执行尚未执行的操作。写代码时给出完整实现。')
CODE_PROMPT = (u'请根据下面的需求写代码。只输出一个 Markdown 代码块，'
               u'代码块内放完整源文件，不要省略实现，也不要在代码块外解释。\n\n')


def to_unicode(value):
    if isinstance(value, unicode):
        return value
    encoding = locale.getpreferredencoding() or 'utf-8'
    try:
        return value.decode(encoding)
    except (UnicodeError, LookupError):
        return value.decode('utf-8', 'replace')


def display(value):
    value = to_unicode(value)
    encoding = sys.stdout.encoding or 'utf-8'
    sys.stdout.write(value.encode(encoding, 'replace'))
    sys.stdout.flush()


def load_env_file(path):
    """Read simple KEY=VALUE lines without executing a shell script."""
    values = {}
    if not os.path.isfile(path):
        return values
    with io.open(path, 'r', encoding='utf-8') as stream:
        for line in stream:
            line = line.strip()
            if line.startswith(u'export '):
                line = line[7:]
            if not line or line.startswith(u'#') or u'=' not in line:
                continue
            name, value = line.split(u'=', 1)
            name = name.strip()
            if not re.match(ur'^[A-Za-z_][A-Za-z0-9_]*$', name):
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in (u'"', u"'"):
                value = value[1:-1]
            values[name] = value
    return values


def config_value(name, files):
    if os.environ.get(name):
        return os.environ[name]
    for values in files:
        if values.get(name):
            return values[name]
    return None


def find_key(files):
    for name in ('GLM_API_KEY', 'ZAI_API_KEY', 'ZHIPUAI_API_KEY',
                 'HERMES_API_KEY'):
        value = config_value(name, files)
        if value:
            return to_unicode(value)
    # Hermes may store a GLM credential under the OpenAI-compatible name.
    # Only accept it when its configured endpoint is visibly a GLM endpoint.
    for values in files:
        if is_glm_url(values.get('OPENAI_BASE_URL', '')) and values.get('OPENAI_API_KEY'):
            return to_unicode(values['OPENAI_API_KEY'])
    if is_glm_url(os.environ.get('OPENAI_BASE_URL', '')):
        value = os.environ.get('OPENAI_API_KEY')
        if value:
            return to_unicode(value)
    return None


def load_key_file(path):
    """Read one raw API key from an absolute path, without logging its value."""
    if not os.path.isabs(path):
        raise ValueError('key 文件路径必须是绝对路径')
    if not os.path.isfile(path):
        raise ValueError('key 文件不存在')
    if os.path.getsize(path) > 4096:
        raise ValueError('key 文件过大')
    try:
        with io.open(path, 'r', encoding='utf-8') as stream:
            value = stream.read().strip()
    except (IOError, OSError, UnicodeError):
        raise ValueError('无法读取 key 文件；请确认它是 UTF-8 文本')
    if (not value or len(value.splitlines()) != 1 or
            any(char.isspace() for char in value) or
            value.startswith(('GLM_API_KEY=', 'OPENAI_API_KEY=',
                              'ZAI_API_KEY=', 'ZHIPUAI_API_KEY='))):
        raise ValueError('key 文件须只包含一行纯 key')
    return value


def is_glm_url(url):
    parsed = urlparse(url)
    host = parsed.hostname or ''
    return (parsed.scheme == 'https' and
            (host == 'bigmodel.cn' or host.endswith('.bigmodel.cn') or
             host == 'z.ai' or host.endswith('.z.ai')))


def completion_url(url):
    url = url.rstrip('/')
    if not url.endswith('/chat/completions'):
        url += '/chat/completions'
    return url


def glm_openai_url(files):
    value = os.environ.get('OPENAI_BASE_URL', '')
    if is_glm_url(value):
        return value
    for values in files:
        value = values.get('OPENAI_BASE_URL', '')
        if is_glm_url(value):
            return value
    return None


def chat(api_url, key, model, messages):
    payload = json.dumps({'model': model, 'messages': messages,
                          'stream': False, 'tools': SCHEMAS,
                          'tool_choice': 'auto'}, ensure_ascii=False).encode('utf-8')
    request = urllib2.Request(api_url, payload, {
        'Authorization': b'Bearer ' + key.encode('utf-8'),
        'Content-Type': 'application/json'
    })
    try:
        response = urllib2.urlopen(request, timeout=90)
        try:
            data = response.read()
        finally:
            response.close()
    except urllib2.HTTPError as exc:
        # Avoid printing request details, which can contain the API key.
        raise RuntimeError('HTTP %s；请检查 key、接口地址和模型名' % exc.code)
    except urllib2.URLError as exc:
        raise RuntimeError('连接失败：%s' % to_unicode(str(exc.reason)).encode('utf-8'))
    try:
        result = json.loads(data)
        message = result['choices'][0]['message']
        if not isinstance(message, dict):
            raise ValueError('bad message')
        return message
    except (ValueError, KeyError, IndexError, TypeError):
        raise RuntimeError('接口返回格式无法识别；请检查接口地址和模型名')


def extract_code(reply):
    match = re.search(ur'```[^\n]*\n(.*?)\n```', reply, re.S)
    if match:
        return match.group(1).rstrip() + u'\n'
    return reply.rstrip() + u'\n'


def save_code(path, code, project):
    path = project.resolve(path)
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        raise RuntimeError('目录不存在：%s' % parent)
    if os.path.exists(path):
        answer = raw_input('文件已存在，覆盖？[y/N] ').strip().lower()
        if answer != 'y':
            return False
    with io.open(path, 'w', encoding='utf-8') as stream:
        stream.write(code)
    display(u'已保存：' + to_unicode(path) + u'\n')
    return True


def confirm(action):
    display(u'工具请求：' + to_unicode(action) + u'\n')
    try:
        answer = raw_input('允许？[y/N] ').strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer == 'y'


def agent_turn(api_url, key, model, messages, project):
    tool_count = 0
    for _ in range(8):
        message = chat(api_url, key, model, messages)
        calls = message.get('tool_calls') or []
        if not calls:
            reply = message.get('content')
            if not isinstance(reply, basestring):
                raise RuntimeError('模型没有返回文字内容')
            reply = to_unicode(reply)
            messages.append({'role': 'assistant', 'content': reply})
            return reply
        messages.append({'role': 'assistant', 'content': message.get('content'),
                         'tool_calls': calls})
        for call in calls:
            tool_count += 1
            if tool_count > 8:
                raise RuntimeError('本轮工具调用超过 8 次，请缩小任务后重试')
            call_id = call.get('id')
            function = call.get('function') or {}
            name = function.get('name', '')
            try:
                if not call_id or call.get('type') != 'function':
                    raise ValueError('工具调用格式错误')
                arguments = json.loads(function.get('arguments') or '{}')
                display(u'[工具] ' + to_unicode(name) + u'\n')
                result = project.call(name, arguments)
            except (ValueError, TypeError, IOError, OSError, UnicodeError) as exc:
                result = u'工具错误：' + to_unicode(str(exc))
            messages.append({'role': 'tool', 'tool_call_id': call_id,
                             'content': to_unicode(result)})
    raise RuntimeError('本轮工具调用超过 8 次，请缩小任务后重试')


def main():
    parser = argparse.ArgumentParser(description='Python 2.7 GLM chat/coding agent')
    parser.add_argument('--key-file', help='只包含一行 GLM key 的文件绝对路径')
    parser.add_argument('--hermes-env', help='Hermes 的 .env 文件路径')
    parser.add_argument('--api-url', help='完整的 chat/completions 接口地址')
    parser.add_argument('--model', help='GLM 模型名，例如 glm-4.6')
    parser.add_argument('--workspace', default='.', help='允许操作的项目目录，默认为当前目录')
    args = parser.parse_args()

    paths = [args.hermes_env] if args.hermes_env else [
        '~/.hermes/.env', '~/.config/hermes/.env']
    files = [load_env_file(os.path.expanduser(path)) for path in paths]
    try:
        key = load_key_file(args.key_file) if args.key_file else find_key(files)
    except ValueError as exc:
        parser.error(str(exc))
    if not key:
        parser.error('没有找到 GLM key；使用 --key-file 指向 key 文件绝对路径')
    api_url = completion_url(args.api_url or config_value('GLM_API_URL', files)
                             or glm_openai_url(files) or DEFAULT_URL)
    model = args.model or config_value('GLM_MODEL', files) or 'glm-4.6'
    try:
        project = ProjectTools(args.workspace, confirm)
    except ValueError as exc:
        parser.error(str(exc))
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    last_code = None
    display(u'GLM agent 已启动。工作目录：' + to_unicode(project.root) + u'\n'
            u'直接输入聊天或项目任务；/code 需求 生成代码；'
            u'/save 文件名 保存代码；/clear 清空对话；/quit 退出。\n')

    while True:
        try:
            line = to_unicode(raw_input('> ')).strip()
        except (EOFError, KeyboardInterrupt):
            display(u'\n')
            break
        if not line:
            continue
        if line in (u'/quit', u'/exit'):
            break
        if line == u'/clear':
            messages = messages[:1]
            last_code = None
            display(u'对话已清空。\n')
            continue
        if line.startswith(u'/save '):
            if last_code is None:
                display(u'请先用 /code 生成代码。\n')
                continue
            try:
                save_code(line[6:].strip(), last_code, project)
            except (ValueError, IOError, OSError, RuntimeError) as exc:
                display(u'保存失败：' + to_unicode(str(exc)) + u'\n')
            continue
        coding = line.startswith(u'/code ')
        prompt = CODE_PROMPT + line[6:].strip() if coding else line
        next_messages = messages + [{'role': 'user', 'content': prompt}]
        try:
            reply = agent_turn(api_url, key, model, next_messages, project)
        except RuntimeError as exc:
            display(u'请求失败：' + to_unicode(str(exc)) + u'\n')
            continue
        display(reply + u'\n')
        messages = next_messages
        if len(messages) > 21:
            # Keep complete user/assistant/tool sequences; cap at turn boundaries.
            cut = max(1, len(messages) - 20)
            while cut < len(messages) and messages[cut].get('role') != 'user':
                cut += 1
            messages = messages[:1] + messages[cut:]
        if coding:
            last_code = extract_code(reply)


if __name__ == '__main__':
    main()

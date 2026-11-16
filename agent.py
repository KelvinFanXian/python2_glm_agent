#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Command-line entry point for the Python 2.7 GLM coding agent."""
from __future__ import print_function

import argparse
import io
import os
import sys

from agent_core import CODE_PROMPT, SYSTEM_PROMPT, agent_turn, extract_code
from glm_client import GlmClient
from glm_config import load_config, to_unicode
from project_tools import ProjectTools, SCHEMAS


def display(value):
    value = to_unicode(value)
    encoding = sys.stdout.encoding or 'utf-8'
    sys.stdout.write(value.encode(encoding, 'replace'))
    sys.stdout.flush()


def confirm(action):
    display(u'工具请求：' + to_unicode(action) + u'\n')
    try:
        answer = raw_input('允许？[y/N] ').strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer == 'y'


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


def on_tool(name):
    display(u'[工具] ' + to_unicode(name) + u'\n')


def main():
    parser = argparse.ArgumentParser(description='Python 2.7 GLM chat/coding agent')
    parser.add_argument('--key-file', help='只包含一行 GLM key 的文件绝对路径')
    parser.add_argument('--hermes-env', help='Hermes 的 .env 文件路径')
    parser.add_argument('--api-url', help='完整的 chat/completions 接口地址')
    parser.add_argument('--model', help='GLM 模型名，例如 glm-4.6')
    parser.add_argument('--workspace', default='.', help='允许操作的项目目录，默认为当前目录')
    args = parser.parse_args()

    try:
        config = load_config(args.key_file, args.hermes_env, args.api_url, args.model)
        project = ProjectTools(args.workspace, confirm)
    except ValueError as exc:
        parser.error(str(exc))
    client = GlmClient(config, SCHEMAS)
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
            reply = agent_turn(client, next_messages, project, on_tool)
        except RuntimeError as exc:
            display(u'请求失败：' + to_unicode(str(exc)) + u'\n')
            continue
        display(reply + u'\n')
        messages = next_messages
        if len(messages) > 21:
            cut = max(1, len(messages) - 20)
            while cut < len(messages) and messages[cut].get('role') != 'user':
                cut += 1
            messages = messages[:1] + messages[cut:]
        if coding:
            last_code = extract_code(reply)


if __name__ == '__main__':
    main()

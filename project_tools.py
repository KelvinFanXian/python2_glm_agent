# -*- coding: utf-8 -*-
"""Bounded project tools for Python 2.7."""
from __future__ import print_function

import io
import os
import subprocess
import tempfile
import time


MAX_READ = 12000
MAX_WRITE = 200000
MAX_OUTPUT = 12000
SKIP_DIRS = set(['.git', '.hg', '.svn', 'node_modules', '__pycache__'])


SCHEMAS = [
    {'type': 'function', 'function': {'name': 'list_files',
     'description': 'List files and folders inside the project workspace.',
     'parameters': {'type': 'object', 'properties': {
         'path': {'type': 'string', 'description': 'Relative directory path; use . for root.'}},
         'required': ['path']}}},
    {'type': 'function', 'function': {'name': 'read_file',
     'description': 'Read a UTF-8 text file inside the workspace (at most 12000 characters).',
     'parameters': {'type': 'object', 'properties': {
         'path': {'type': 'string', 'description': 'Relative file path.'}},
         'required': ['path']}}},
    {'type': 'function', 'function': {'name': 'search_text',
     'description': 'Search UTF-8 project files for a literal string.',
     'parameters': {'type': 'object', 'properties': {
         'text': {'type': 'string', 'description': 'Literal text to find.'}},
         'required': ['text']}}},
    {'type': 'function', 'function': {'name': 'write_file',
     'description': 'Create or replace a UTF-8 file inside the workspace. Parent folder must exist.',
     'parameters': {'type': 'object', 'properties': {
         'path': {'type': 'string'}, 'content': {'type': 'string'}},
         'required': ['path', 'content']}}},
    {'type': 'function', 'function': {'name': 'edit_file',
     'description': 'Replace exactly one occurrence of old_text in a UTF-8 file.',
     'parameters': {'type': 'object', 'properties': {
         'path': {'type': 'string'}, 'old_text': {'type': 'string'},
         'new_text': {'type': 'string'}},
         'required': ['path', 'old_text', 'new_text']}}},
    {'type': 'function', 'function': {'name': 'run_command',
     'description': 'Run a shell command in the workspace, with user confirmation and a 30-second limit.',
     'parameters': {'type': 'object', 'properties': {
         'command': {'type': 'string'}}, 'required': ['command']}}}
]


def clipped(value, limit):
    if len(value) <= limit:
        return value
    return value[:limit] + u'\n[输出已截断]'


class ProjectTools(object):
    def __init__(self, root, confirm):
        self.root = os.path.realpath(os.path.abspath(root))
        if not os.path.isdir(self.root):
            raise ValueError('工作目录不存在')
        self.confirm = confirm

    def resolve(self, path):
        if not isinstance(path, basestring) or not path:
            raise ValueError('路径不能为空')
        target = os.path.realpath(os.path.join(self.root, path))
        if target != self.root and not target.startswith(self.root + os.sep):
            raise ValueError('路径超出工作目录')
        relative = os.path.relpath(target, self.root)
        parts = relative.split(os.sep)
        if any(part in SKIP_DIRS for part in parts):
            raise ValueError('不允许访问此目录')
        base = os.path.basename(target).lower()
        if base == '.env' or base.startswith('.env.') or base in (
                'id_rsa', 'id_ed25519', 'credentials', 'credentials.json'):
            raise ValueError('不允许访问密钥文件')
        return target

    def list_files(self, path):
        target = self.resolve(path)
        if not os.path.isdir(target):
            raise ValueError('目录不存在')
        result = []
        for name in sorted(os.listdir(target)):
            try:
                child = self.resolve(os.path.join(path, name))
            except ValueError:
                continue
            result.append(name + ('/' if os.path.isdir(child) else ''))
            if len(result) >= 200:
                result.append('[仅显示前 200 项]')
                break
        return u'\n'.join(result) or u'[空目录]'

    def read_file(self, path):
        target = self.resolve(path)
        if not os.path.isfile(target):
            raise ValueError('文件不存在')
        if os.path.getsize(target) > MAX_READ * 4:
            raise ValueError('文件过大，请缩小读取范围')
        with io.open(target, 'r', encoding='utf-8') as stream:
            return clipped(stream.read(), MAX_READ)

    def search_text(self, text):
        if not isinstance(text, basestring) or not text or len(text) > 200:
            raise ValueError('搜索文字长度须为 1 到 200 字')
        found = []
        visited = 0
        for directory, dirs, files in os.walk(self.root):
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
            for name in files:
                relative = os.path.relpath(os.path.join(directory, name), self.root)
                try:
                    target = self.resolve(relative)
                    if os.path.getsize(target) > MAX_READ * 4:
                        continue
                    with io.open(target, 'r', encoding='utf-8') as stream:
                        lines = stream.readlines()
                except (ValueError, IOError, OSError, UnicodeError):
                    continue
                visited += 1
                for number, line in enumerate(lines, 1):
                    if text in line:
                        found.append(u'%s:%s: %s' % (
                            relative, number, line.strip()[:200]))
                        if len(found) >= 100:
                            return u'\n'.join(found) + u'\n[仅显示前 100 项]'
                if visited >= 300:
                    return (u'\n'.join(found) or u'[未找到]') + u'\n[仅搜索前 300 个文件]'
        return u'\n'.join(found) or u'[未找到]'

    def write_file(self, path, content):
        target = self.resolve(path)
        if not isinstance(content, basestring) or len(content) > MAX_WRITE:
            raise ValueError('内容不是文字或超过 200000 字')
        if not os.path.isdir(os.path.dirname(target)):
            raise ValueError('父目录不存在')
        if os.path.isdir(target):
            raise ValueError('目标是目录')
        if os.path.exists(target) and not self.confirm(u'覆盖文件 ' + path):
            return u'用户拒绝覆盖'
        with io.open(target, 'w', encoding='utf-8') as stream:
            stream.write(content)
        return u'已写入 ' + path

    def edit_file(self, path, old_text, new_text):
        target = self.resolve(path)
        if not os.path.isfile(target) or not old_text:
            raise ValueError('文件不存在或 old_text 为空')
        with io.open(target, 'r', encoding='utf-8') as stream:
            content = stream.read()
        if content.count(old_text) != 1:
            raise ValueError('old_text 必须在文件中恰好出现一次')
        updated = content.replace(old_text, new_text, 1)
        if len(updated) > MAX_WRITE:
            raise ValueError('修改后的文件过大')
        if not self.confirm(u'修改文件 ' + path):
            return u'用户拒绝修改'
        with io.open(target, 'w', encoding='utf-8') as stream:
            stream.write(updated)
        return u'已修改 ' + path

    def run_command(self, command):
        if not isinstance(command, basestring) or not command or len(command) > 1000:
            raise ValueError('命令长度须为 1 到 1000 字')
        if not self.confirm(u'在工作目录运行：' + command):
            return u'用户拒绝运行命令'
        allowed = ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'USER', 'SHELL',
                   'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT')
        env = dict((name, os.environ[name]) for name in allowed if name in os.environ)
        output = tempfile.TemporaryFile()
        try:
            with open(os.devnull, 'rb') as empty_input:
                process = subprocess.Popen(command, shell=True,
                    cwd=self.root, env=env, stdin=empty_input,
                    stdout=output, stderr=subprocess.STDOUT)
                deadline = time.time() + 30
                while process.poll() is None and time.time() < deadline:
                    time.sleep(0.1)
                timed_out = process.poll() is None
                if timed_out:
                    process.terminate()
                    time.sleep(0.2)
                    if process.poll() is None:
                        process.kill()
                    process.wait()
            output.seek(0)
            data = output.read(MAX_OUTPUT + 1)
        finally:
            output.close()
        decoded = data.decode('utf-8', 'replace')
        status = u'超时' if timed_out else u'退出码 %s' % process.returncode
        return status + u'\n' + clipped(decoded, MAX_OUTPUT)

    def call(self, name, arguments):
        methods = {
            'list_files': (self.list_files, ('path',)),
            'read_file': (self.read_file, ('path',)),
            'search_text': (self.search_text, ('text',)),
            'write_file': (self.write_file, ('path', 'content')),
            'edit_file': (self.edit_file, ('path', 'old_text', 'new_text')),
            'run_command': (self.run_command, ('command',))}
        if name not in methods or not isinstance(arguments, dict):
            raise ValueError('未知工具或参数格式错误')
        method, keys = methods[name]
        if any(key not in arguments for key in keys):
            raise ValueError('缺少必填参数')
        return method(*(arguments[key] for key in keys))

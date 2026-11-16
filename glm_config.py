# -*- coding: utf-8 -*-
"""GLM credentials, model selection, and endpoint configuration."""
import io
import locale
import os
import re
from urlparse import urlparse


DEFAULT_URL = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
DEFAULT_MODEL = 'glm-4.6'


def to_unicode(value):
    if isinstance(value, unicode):
        return value
    encoding = locale.getpreferredencoding() or 'utf-8'
    try:
        return value.decode(encoding)
    except (UnicodeError, LookupError):
        return value.decode('utf-8', 'replace')


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


def is_glm_url(url):
    parsed = urlparse(url)
    host = parsed.hostname or ''
    return (parsed.scheme == 'https' and
            (host == 'bigmodel.cn' or host.endswith('.bigmodel.cn') or
             host == 'z.ai' or host.endswith('.z.ai')))


def find_key(files):
    for name in ('GLM_API_KEY', 'ZAI_API_KEY', 'ZHIPUAI_API_KEY',
                 'HERMES_API_KEY'):
        value = config_value(name, files)
        if value:
            return to_unicode(value)
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


class GlmConfig(object):
    def __init__(self, key, api_url, model):
        self.key = key
        self.api_url = api_url
        self.model = model


def load_config(key_file=None, hermes_env=None, api_url=None, model=None):
    paths = [hermes_env] if hermes_env else [
        '~/.hermes/.env', '~/.config/hermes/.env']
    files = [load_env_file(os.path.expanduser(path)) for path in paths]
    key = load_key_file(key_file) if key_file else find_key(files)
    if not key:
        raise ValueError('没有找到 GLM key；使用 --key-file 指向 key 文件绝对路径')
    url = completion_url(api_url or config_value('GLM_API_URL', files)
                         or glm_openai_url(files) or DEFAULT_URL)
    selected_model = model or config_value('GLM_MODEL', files) or DEFAULT_MODEL
    return GlmConfig(key, url, selected_model)

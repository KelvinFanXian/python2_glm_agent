# -*- coding: utf-8 -*-
"""HTTP connection to GLM Chat Completions; no CLI or filesystem logic."""
import json
import urllib2

from glm_config import to_unicode


class GlmClient(object):
    def __init__(self, config, tools):
        self.config = config
        self.tools = tools

    def chat(self, messages):
        payload = json.dumps({
            'model': self.config.model, 'messages': messages, 'stream': False,
            'tools': self.tools, 'tool_choice': 'auto'
        }, ensure_ascii=False).encode('utf-8')
        request = urllib2.Request(self.config.api_url, payload, {
            'Authorization': b'Bearer ' + self.config.key.encode('utf-8'),
            'Content-Type': 'application/json'
        })
        try:
            response = urllib2.urlopen(request, timeout=90)
            try:
                data = response.read()
            finally:
                response.close()
        except urllib2.HTTPError as exc:
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

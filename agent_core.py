# -*- coding: utf-8 -*-
"""Conversation prompts and the model/tool interaction loop."""
import json
import re

from glm_config import to_unicode


SYSTEM_PROMPT = (u'你是一个实用的编程助手。回答要准确、简洁。'
                 u'需要了解或修改项目时，调用提供的工具；先读取相关文件，再修改。'
                 u'不要假称已执行尚未执行的操作。写代码时给出完整实现。')
CODE_PROMPT = (u'请根据下面的需求写代码。只输出一个 Markdown 代码块，'
               u'代码块内放完整源文件，不要省略实现，也不要在代码块外解释。\n\n')


def extract_code(reply):
    match = re.search(ur'```[^\n]*\n(.*?)\n```', reply, re.S)
    if match:
        return match.group(1).rstrip() + u'\n'
    return reply.rstrip() + u'\n'


def agent_turn(client, messages, project, on_tool=None):
    tool_count = 0
    for _ in range(8):
        message = client.chat(messages)
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
                if on_tool:
                    on_tool(name)
                result = project.call(name, arguments)
            except (ValueError, TypeError, IOError, OSError, UnicodeError) as exc:
                result = u'工具错误：' + to_unicode(str(exc))
            messages.append({'role': 'tool', 'tool_call_id': call_id,
                             'content': to_unicode(result)})
    raise RuntimeError('本轮工具调用超过 8 次，请缩小任务后重试')

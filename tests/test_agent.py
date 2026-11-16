# -*- coding: utf-8 -*-
"""Offline tests. Run with: python2.7 -m unittest discover -s tests"""
from __future__ import print_function

import io
import json
import os
import shutil
import tempfile
import unittest

import agent
from project_tools import ProjectTools, SCHEMAS


class ProjectToolTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.actions = []
        self.allowed = True
        self.project = ProjectTools(self.root, self.confirm)
        self.write('sample.txt', u'第一行\nsecond line\n')

    def tearDown(self):
        shutil.rmtree(self.root)

    def confirm(self, action):
        self.actions.append(action)
        return self.allowed

    def write(self, name, content):
        with io.open(os.path.join(self.root, name), 'w', encoding='utf-8') as stream:
            stream.write(content)

    def test_list_read_search(self):
        self.assertIn('sample.txt', self.project.list_files('.'))
        self.assertIn(u'第一行', self.project.read_file('sample.txt'))
        self.assertIn('sample.txt:2', self.project.search_text('second'))

    def test_write_edit_and_confirmation(self):
        self.assertEqual(self.project.write_file('new.py', u'print(1)\n'),
                         u'已写入 new.py')
        self.assertEqual(self.project.edit_file('new.py', u'print(1)',
                                                u'print(2)'), u'已修改 new.py')
        self.assertTrue(self.actions)
        self.allowed = False
        self.assertEqual(self.project.write_file('new.py', u'bad'), u'用户拒绝覆盖')
        self.assertEqual(self.project.edit_file('new.py', u'print(2)',
                                                u'bad'), u'用户拒绝修改')
        self.assertIn('print(2)', self.project.read_file('new.py'))

    def test_paths_and_secrets_are_blocked(self):
        for path in ('../outside.txt', '.env', '.env.local', '.git/config'):
            self.assertRaises(ValueError, self.project.resolve, path)
        self.assertRaises(ValueError, self.project.edit_file,
                          'sample.txt', u'not present', u'x')

    def test_command_requires_confirmation(self):
        self.allowed = False
        self.assertEqual(self.project.run_command('echo hello'),
                         u'用户拒绝运行命令')
        self.allowed = True
        result = self.project.run_command('echo hello')
        self.assertIn('hello', result)
        self.assertIn(u'退出码 0', result)

    def test_all_schemas_have_dispatchers(self):
        names = set(item['function']['name'] for item in SCHEMAS)
        self.assertEqual(names, set(('list_files', 'read_file', 'search_text',
                                     'write_file', 'edit_file', 'run_command')))


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.project = ProjectTools(self.root, lambda action: True)
        with io.open(os.path.join(self.root, 'sample.txt'), 'w',
                     encoding='utf-8') as stream:
            stream.write(u'hello')
        self.old_chat = agent.chat
        self.old_display = agent.display
        agent.display = lambda value: None

    def tearDown(self):
        agent.chat = self.old_chat
        agent.display = self.old_display
        shutil.rmtree(self.root)

    def test_tool_call_then_final_answer(self):
        replies = iter([
            {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'call_1', 'type': 'function', 'function': {
                    'name': 'read_file', 'arguments': '{"path":"sample.txt"}'}}]},
            {'role': 'assistant', 'content': u'读取完成'}])
        agent.chat = lambda *args: next(replies)
        messages = [{'role': 'system', 'content': u'helper'},
                    {'role': 'user', 'content': u'读取文件'}]
        self.assertEqual(agent.agent_turn('url', 'key', 'model', messages,
                                          self.project), u'读取完成')
        self.assertEqual(messages[-2]['role'], 'tool')
        self.assertEqual(messages[-2]['tool_call_id'], 'call_1')
        self.assertEqual(messages[-2]['content'], u'hello')

    def test_bad_tool_arguments_return_error_to_model(self):
        replies = iter([
            {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'call_2', 'type': 'function', 'function': {
                    'name': 'read_file', 'arguments': '{bad json'}}]},
            {'role': 'assistant', 'content': u'参数有误'}])
        agent.chat = lambda *args: next(replies)
        messages = [{'role': 'system', 'content': u'helper'},
                    {'role': 'user', 'content': u'读取文件'}]
        agent.agent_turn('url', 'key', 'model', messages, self.project)
        self.assertIn(u'工具错误', messages[-2]['content'])

    def test_save_stays_in_workspace(self):
        agent.save_code('out.py', u'print(1)\n', self.project)
        self.assertEqual(self.project.read_file('out.py'), u'print(1)\n')
        self.assertRaises(ValueError, agent.save_code, '../outside.py',
                          u'bad', self.project)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.old_urlopen = agent.urllib2.urlopen

    def tearDown(self):
        agent.urllib2.urlopen = self.old_urlopen

    def test_request_includes_six_tools_and_messages(self):
        seen = {}

        class Response(object):
            def read(self):
                return json.dumps({'choices': [{'message': {
                    'role': 'assistant', 'content': u'hello'}}]})

            def close(self):
                pass

        def fake_urlopen(request, timeout):
            seen['body'] = json.loads(request.data)
            seen['timeout'] = timeout
            return Response()

        agent.urllib2.urlopen = fake_urlopen
        message = agent.chat(agent.DEFAULT_URL, u'test-key', 'glm-4.6',
                             [{'role': 'user', 'content': u'你好'}])
        self.assertEqual(message['content'], u'hello')
        self.assertEqual(seen['body']['messages'][0]['content'], u'你好')
        self.assertEqual(len(seen['body']['tools']), 6)
        self.assertEqual(seen['body']['tool_choice'], 'auto')
        self.assertEqual(seen['timeout'], 90)

    def test_unexpected_response_is_rejected(self):
        class Response(object):
            def read(self):
                return '{}'

            def close(self):
                pass

        agent.urllib2.urlopen = lambda request, timeout: Response()
        self.assertRaises(RuntimeError, agent.chat, agent.DEFAULT_URL,
                          u'test-key', 'glm-4.6', [])


class KeyFileTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.path = os.path.join(self.root, 'key')

    def tearDown(self):
        shutil.rmtree(self.root)

    def put(self, value):
        with io.open(self.path, 'w', encoding='utf-8') as stream:
            stream.write(value)

    def test_reads_single_raw_key_from_absolute_path(self):
        self.put(u'example-id.example-secret\n')
        self.assertEqual(agent.load_key_file(self.path),
                         u'example-id.example-secret')

    def test_rejects_relative_path_and_env_format(self):
        self.assertRaises(ValueError, agent.load_key_file, 'key')
        self.put(u'GLM_API_KEY=example-secret\n')
        self.assertRaises(ValueError, agent.load_key_file, self.path)
        self.put(u'first\nsecond\n')
        self.assertRaises(ValueError, agent.load_key_file, self.path)


if __name__ == '__main__':
    unittest.main()

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
import agent_core
import glm_client
import glm_config
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
        self.old_display = agent.display
        agent.display = lambda value: None

    def tearDown(self):
        agent.display = self.old_display
        shutil.rmtree(self.root)

    def client_with(self, replies):
        class FakeClient(object):
            def __init__(self, items):
                self.items = iter(items)

            def chat(self, messages):
                return next(self.items)

        return FakeClient(replies)

    def test_tool_call_then_final_answer(self):
        client = self.client_with([
            {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'call_1', 'type': 'function', 'function': {
                    'name': 'read_file', 'arguments': '{"path":"sample.txt"}'}}]},
            {'role': 'assistant', 'content': u'读取完成'}])
        messages = [{'role': 'system', 'content': u'helper'},
                    {'role': 'user', 'content': u'读取文件'}]
        self.assertEqual(agent_core.agent_turn(client, messages, self.project),
                         u'读取完成')
        self.assertEqual(messages[-2]['role'], 'tool')
        self.assertEqual(messages[-2]['tool_call_id'], 'call_1')
        self.assertEqual(messages[-2]['content'], u'hello')

    def test_bad_tool_arguments_return_error_to_model(self):
        client = self.client_with([
            {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'call_2', 'type': 'function', 'function': {
                    'name': 'read_file', 'arguments': '{bad json'}}]},
            {'role': 'assistant', 'content': u'参数有误'}])
        messages = [{'role': 'system', 'content': u'helper'},
                    {'role': 'user', 'content': u'读取文件'}]
        agent_core.agent_turn(client, messages, self.project)
        self.assertIn(u'工具错误', messages[-2]['content'])

    def test_save_stays_in_workspace(self):
        agent.save_code('out.py', u'print(1)\n', self.project)
        self.assertEqual(self.project.read_file('out.py'), u'print(1)\n')
        self.assertRaises(ValueError, agent.save_code, '../outside.py',
                          u'bad', self.project)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.old_urlopen = glm_client.urllib2.urlopen

    def tearDown(self):
        glm_client.urllib2.urlopen = self.old_urlopen

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

        glm_client.urllib2.urlopen = fake_urlopen
        config = glm_config.GlmConfig(u'test-key', glm_config.DEFAULT_URL,
                                      'glm-4.6')
        message = glm_client.GlmClient(config, SCHEMAS).chat(
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

        glm_client.urllib2.urlopen = lambda request, timeout: Response()
        config = glm_config.GlmConfig(u'test-key', glm_config.DEFAULT_URL,
                                      'glm-4.6')
        self.assertRaises(RuntimeError, glm_client.GlmClient(config, SCHEMAS).chat, [])


class KeyFileTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.path = os.path.join(self.root, 'key')
        names = ('GLM_API_KEY', 'ZAI_API_KEY', 'ZHIPUAI_API_KEY',
                 'HERMES_API_KEY', 'GLM_MODEL', 'GLM_API_URL',
                 'OPENAI_BASE_URL', 'OPENAI_API_KEY')
        self.old_env = dict((name, os.environ.get(name)) for name in names)
        for name in names:
            os.environ.pop(name, None)

    def tearDown(self):
        for name, value in self.old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.root)

    def put(self, value):
        with io.open(self.path, 'w', encoding='utf-8') as stream:
            stream.write(value)

    def test_reads_single_raw_key_from_absolute_path(self):
        self.put(u'example-id.example-secret\n')
        self.assertEqual(glm_config.load_key_file(self.path),
                         u'example-id.example-secret')

    def test_rejects_relative_path_and_env_format(self):
        self.assertRaises(ValueError, glm_config.load_key_file, 'key')
        self.put(u'GLM_API_KEY=example-secret\n')
        self.assertRaises(ValueError, glm_config.load_key_file, self.path)
        self.put(u'first\nsecond\n')
        self.assertRaises(ValueError, glm_config.load_key_file, self.path)

    def test_config_prefers_key_file_and_uses_env_model(self):
        self.put(u'file-secret\n')
        env_path = os.path.join(self.root, '.env')
        with io.open(env_path, 'w', encoding='utf-8') as stream:
            stream.write(u'GLM_API_KEY=env-secret\n'
                         u'GLM_API_URL=https://api.z.ai/api/paas/v4\n'
                         u'GLM_MODEL=glm-test\n')
        config = glm_config.load_config(self.path, env_path)
        self.assertEqual(config.key, u'file-secret')
        self.assertEqual(config.api_url,
                         'https://api.z.ai/api/paas/v4/chat/completions')
        self.assertEqual(config.model, 'glm-test')

    def test_default_coding_plan_model_and_url(self):
        self.put(u'file-secret\n')
        config = glm_config.load_config(self.path,
                                        os.path.join(self.root, 'missing.env'))
        self.assertEqual(config.api_url,
                         'https://open.bigmodel.cn/api/coding/paas/v4/chat/completions')
        self.assertEqual(config.model, 'glm-5.3-flash')

    def test_example_matches_default_config(self):
        example = os.path.join(os.path.dirname(__file__), '..', '.env.example')
        values = glm_config.load_env_file(example)
        self.assertEqual(glm_config.completion_url(values['GLM_API_URL']),
                         glm_config.DEFAULT_URL)
        self.assertEqual(values['GLM_MODEL'], glm_config.DEFAULT_MODEL)


if __name__ == '__main__':
    unittest.main()

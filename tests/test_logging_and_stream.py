import io
import logging
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from devteam.utils import logging_utils
from devteam.utils.stream_handler import StreamHandler


# =====================================================================
# logging_utils
# =====================================================================

def _record(msg, level=logging.INFO, name='devteam'):
    return logging.LogRecord(name, level, __file__, 1, msg, None, None)


class TestWildcardMatch:
    def test_simple_substring(self):
        assert logging_utils._wildcard_match('error', 'an Error happened')

    def test_no_match(self):
        assert not logging_utils._wildcard_match('xyz', 'abc')

    def test_wildcard_pattern(self):
        assert logging_utils._wildcard_match('start*project', 'Starting a new project')

    def test_wildcard_pattern_out_of_order(self):
        assert not logging_utils._wildcard_match('project*start', 'Starting a new project')

    def test_wildcard_with_empty_segment(self):
        assert logging_utils._wildcard_match('*done', 'all done')


class TestIconFor:
    def test_message_icon_match(self):
        assert logging_utils._icon_for(_record('Starting new project xyz')) == '🚀'

    def test_level_icon_fallback(self):
        assert logging_utils._icon_for(_record('random', level=logging.ERROR)) == '❌'

    def test_no_icon(self):
        assert logging_utils._icon_for(_record('plain info message')) == ''


class TestConsoleFormatter:
    def test_root_logger_uses_message_only(self):
        fmt = logging_utils.ConsoleDispatchFormatter()
        rec = _record('hello', name='root')
        assert fmt.format(rec) == 'hello'

    def test_named_logger_with_icon(self):
        fmt = logging_utils.ConsoleDispatchFormatter()
        rec = _record('Rate limit reached now', name='devteam.rate')
        out = fmt.format(rec)
        assert '⏳' in out
        assert 'devteam.rate' in out

    def test_named_logger_without_icon(self):
        fmt = logging_utils.ConsoleDispatchFormatter()
        rec = _record('plain', name='devteam.x')
        out = fmt.format(rec)
        assert out == 'devteam.x: plain'


class TestHandlers:
    def test_setup_file_handler(self, tmp_path):
        log_file = tmp_path / 'test.log'
        handler = logging_utils.setup_file_handler(log_file)
        assert isinstance(handler, logging.Handler)
        handler.close()

    def test_setup_file_handler_with_rollover(self, tmp_path):
        log_file = tmp_path / 'roll.log'
        log_file.write_text('existing', encoding='utf-8')
        handler = logging_utils.setup_file_handler(log_file, do_rollover=True)
        handler.close()

    def test_add_and_remove_file_handler(self, tmp_path):
        log_file = tmp_path / 'add.log'
        handler = logging_utils.add_file_handler(log_file)
        assert handler in logging.getLogger().handlers
        logging_utils.remove_file_handler(handler)
        assert handler not in logging.getLogger().handlers
        handler.close()

    def test_setup_logging_configures_handlers(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        logging_utils.setup_logging(console_level=logging.INFO)
        # Noisy loggers are muted to WARNING.
        assert logging.getLogger('httpx').level == logging.WARNING

    def test_setup_logging_no_console(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        logging_utils.setup_logging(console_level=None)
        assert logging.getLogger('werkzeug').level == logging.WARNING


# =====================================================================
# StreamHandler
# =====================================================================

def _chunk_with_reasoning(reasoning):
    chunk = MagicMock()
    chunk.message.additional_kwargs = {'reasoning_content': reasoning}
    return chunk


class TestStreamHandler:
    def test_non_string_token_ignored(self):
        buf = io.StringIO()
        h = StreamHandler(file=buf)
        h.on_llm_new_token(None)
        assert buf.getvalue() == ''

    def test_plain_token_written_to_file(self):
        buf = io.StringIO()
        h = StreamHandler(file=buf)
        h.on_llm_new_token('hello')
        assert buf.getvalue() == 'hello'

    def test_reasoning_token_written_to_file(self):
        buf = io.StringIO()
        h = StreamHandler(file=buf)
        h.on_llm_new_token('', chunk=_chunk_with_reasoning('thinking...'))
        assert 'thinking...' in buf.getvalue()
        assert h._in_thinking is True

    def test_transition_out_of_thinking(self):
        buf = io.StringIO()
        h = StreamHandler(file=buf)
        h.on_llm_new_token('', chunk=_chunk_with_reasoning('think'))
        h.on_llm_new_token('answer', chunk=MagicMock(message=MagicMock(additional_kwargs={})))
        assert h._in_thinking is False
        assert 'answer' in buf.getvalue()

    def test_queue_mode_emits_tokens(self):
        from queue import Queue
        q = Queue()
        h = StreamHandler(queue=q)
        h.on_llm_new_token('tok')
        item = q.get_nowait()
        assert item['token'] == 'tok'
        assert item['is_thinking'] is False

    def test_queue_mode_emits_reasoning(self):
        from queue import Queue
        q = Queue()
        h = StreamHandler(queue=q)
        h.on_llm_new_token('', chunk=_chunk_with_reasoning('deep thought'))
        item = q.get_nowait()
        assert item['is_thinking'] is True

    def test_on_llm_end_file(self):
        buf = io.StringIO()
        h = StreamHandler(file=buf)
        h._in_thinking = True
        h.on_llm_end(None)
        assert buf.getvalue() == '\n'
        assert h._in_thinking is False

    def test_on_llm_end_queue(self):
        from queue import Queue
        q = Queue()
        h = StreamHandler(queue=q)
        h.on_llm_end(None)
        assert q.get_nowait()['token'] == '\n'

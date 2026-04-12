import sys
import time
from langchain_core.callbacks import BaseCallbackHandler

class StreamHandler(BaseCallbackHandler):
    """Streams raw LLM token output (including thinking) to the console or a queue."""

    def __init__(self, file=None, queue=None):
        self._file = file or sys.stderr
        self._queue = queue
        self._in_thinking = False

    def _emit_to_queue(self, token: str, is_thinking: bool):
        self._queue.put({
            'type': 'thinking_token',
            'ts': time.time(),
            'token': token,
            'is_thinking': is_thinking,
        })

    def on_llm_new_token(self, token, **kwargs) -> None:
        if not isinstance(token, str):
            return
        chunk = kwargs.get('chunk')
        if chunk and hasattr(chunk, 'message'):
            reasoning = chunk.message.additional_kwargs.get('reasoning_content', '')
            if reasoning:
                if not self._in_thinking:
                    self._in_thinking = True
                if self._queue:
                    self._emit_to_queue(reasoning, is_thinking=True)
                else:
                    self._file.write(reasoning)
                    self._file.flush()
                return
            if self._in_thinking:
                self._in_thinking = False
        if self._queue:
            self._emit_to_queue(token, is_thinking=False)
        else:
            self._file.write(token)
            self._file.flush()

    def on_llm_end(self, response, **kwargs) -> None:
        if self._in_thinking:
            self._in_thinking = False
        if self._queue:
            self._emit_to_queue('\n', is_thinking=False)
        else:
            self._file.write("\n")
            self._file.flush()

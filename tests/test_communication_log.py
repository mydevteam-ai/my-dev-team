import pytest
from devteam.utils.communication_log import CommunicationLog

class DummyLogger(CommunicationLog):
    pass

def test_communication_with_string():
    logger = DummyLogger()
    result = logger.communication("Hello world!")
    assert result == ["**[DummyLogger]**: Hello world!"]

@pytest.mark.parametrize("messages,expected", [
    (["msg1", "msg2"], ["**[DummyLogger]**: msg1", "**[DummyLogger]**: msg2"]),
    ([], []),
    (["msg1", "", "  ", "msg2"], ["**[DummyLogger]**: msg1", "**[DummyLogger]**: msg2"]),
])
def test_communication_with_list(messages, expected):
    logger = DummyLogger()
    result = logger.communication(messages)
    assert result == expected

@pytest.mark.parametrize("message", ["", "   ", "\n\n"])
def test_communication_skips_empty_string(message):
    logger = DummyLogger()
    assert logger.communication(message) == []

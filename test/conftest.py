import pytest


@pytest.fixture
def logger_mock(mocker):
    return mocker.MagicMock(
        name="mock_logger", spec=["warning", "info", "debug", "getChild"]
    )

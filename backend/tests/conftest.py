"""Keep all backend tests independent of credentials and the OpenAI network."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def offline_openai():
    with patch("codenames.gpt.chat_gpt.openai.AsyncOpenAI"):
        yield


@pytest.fixture(autouse=True)
def sessions():
    from tests.helpers import reset_connections
    reset_connections()

"""Keep all backend tests independent of credentials and the OpenAI network."""

import os
from unittest.mock import patch

import pytest


# options.py validates the key at import time, before fixtures can run.
os.environ["OPENAI_KEY"] = "test-key-not-a-real-credential"


@pytest.fixture(autouse=True)
def offline_openai():
    with patch("codenames.gpt.chat_gpt.openai.AsyncOpenAI"):
        yield

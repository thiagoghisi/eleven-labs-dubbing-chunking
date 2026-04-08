"""Unit tests for tts.py — cost estimation and API client (mocked)."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import requests

from dub_chunk.models import Paragraph, VoiceConfig
from dub_chunk.tts import estimate_cost, generate_clip


def _p(id, speaker, text):
    return Paragraph(id=id, speaker=speaker, text=text)


# ======================================================================
# estimate_cost — pure logic, no mocking needed
# ======================================================================


class TestEstimateCost:

    def test_basic_cost_calculation(self):
        paras = [_p(1, "A", "x" * 1000)]  # 1000 chars
        result = estimate_cost(paras)
        assert result["characters"] == 1000
        assert result["estimated_cost_usd"] == 0.30

    def test_cost_scales_linearly(self):
        paras = [_p(1, "A", "x" * 5000)]  # 5000 chars
        result = estimate_cost(paras)
        assert result["estimated_cost_usd"] == 1.50

    def test_multiple_paragraphs_summed(self):
        paras = [
            _p(1, "A", "x" * 500),
            _p(2, "B", "y" * 500),
        ]
        result = estimate_cost(paras)
        assert result["characters"] == 1000
        assert result["estimated_cost_usd"] == 0.30

    def test_empty_paragraphs(self):
        paras = [_p(1, "A", "")]
        result = estimate_cost(paras)
        assert result["characters"] == 0
        assert result["estimated_cost_usd"] == 0.0

    def test_empty_list(self):
        result = estimate_cost([])
        assert result["characters"] == 0
        assert result["estimated_cost_usd"] == 0.0

    def test_cost_rounded_to_four_decimals(self):
        paras = [_p(1, "A", "x" * 7)]  # 7 chars → 0.0021
        result = estimate_cost(paras)
        assert result["estimated_cost_usd"] == 0.0021


# ======================================================================
# generate_clip — mocked HTTP
# ======================================================================


class TestGenerateClip:

    @pytest.fixture
    def voice_config(self):
        return VoiceConfig(voice_id="test_voice_123")

    @pytest.fixture
    def output_path(self, tmp_path):
        return tmp_path / "output.mp3"

    @patch("dub_chunk.tts.requests.post")
    def test_successful_generation(self, mock_post, voice_config, output_path):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake mp3 bytes"
        mock_post.return_value = mock_response

        result = generate_clip(
            text="Hello world",
            voice_config=voice_config,
            api_key="test_key",
            output_path=output_path,
        )

        assert result == output_path
        assert output_path.exists()
        assert output_path.read_bytes() == b"fake mp3 bytes"

    @patch("dub_chunk.tts.requests.post")
    def test_correct_api_url(self, mock_post, voice_config, output_path):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"data"
        mock_post.return_value = mock_response

        generate_clip("text", voice_config, "key", output_path)

        call_url = mock_post.call_args[0][0]
        assert "test_voice_123" in call_url

    @patch("dub_chunk.tts.requests.post")
    def test_api_key_in_headers(self, mock_post, voice_config, output_path):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"data"
        mock_post.return_value = mock_response

        generate_clip("text", voice_config, "my_secret_key", output_path)

        call_headers = mock_post.call_args[1]["headers"]
        assert call_headers["xi-api-key"] == "my_secret_key"

    @patch("dub_chunk.tts.requests.post")
    def test_voice_settings_in_payload(self, mock_post, voice_config, output_path):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"data"
        mock_post.return_value = mock_response

        generate_clip("text", voice_config, "key", output_path)

        payload = mock_post.call_args[1]["json"]
        assert payload["voice_settings"]["stability"] == 0.65
        assert payload["voice_settings"]["similarity_boost"] == 0.80

    @patch("dub_chunk.tts.time.sleep")
    @patch("dub_chunk.tts.requests.post")
    def test_retries_on_429_rate_limit(self, mock_post, mock_sleep, voice_config, output_path):
        rate_limit = MagicMock()
        rate_limit.status_code = 429

        success = MagicMock()
        success.status_code = 200
        success.content = b"data"

        mock_post.side_effect = [rate_limit, success]

        result = generate_clip("text", voice_config, "key", output_path)
        assert result == output_path
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(2.0)

    @patch("dub_chunk.tts.time.sleep")
    @patch("dub_chunk.tts.requests.post")
    def test_retries_on_500_server_error(self, mock_post, mock_sleep, voice_config, output_path):
        error_500 = MagicMock()
        error_500.status_code = 500

        success = MagicMock()
        success.status_code = 200
        success.content = b"data"

        mock_post.side_effect = [error_500, success]

        result = generate_clip("text", voice_config, "key", output_path)
        assert result == output_path

    @patch("dub_chunk.tts.time.sleep")
    @patch("dub_chunk.tts.requests.post")
    def test_exponential_backoff(self, mock_post, mock_sleep, voice_config, output_path):
        error = MagicMock()
        error.status_code = 429

        success = MagicMock()
        success.status_code = 200
        success.content = b"data"

        mock_post.side_effect = [error, error, error, success]

        generate_clip("text", voice_config, "key", output_path)
        assert mock_sleep.call_count == 3
        # Backoff: 2, 4, 8
        calls = [c[0][0] for c in mock_sleep.call_args_list]
        assert calls == [2.0, 4.0, 8.0]

    @patch("dub_chunk.tts.requests.post")
    def test_non_retryable_error_raises_immediately(self, mock_post, voice_config, output_path):
        error_401 = MagicMock()
        error_401.status_code = 401
        error_401.raise_for_status.side_effect = requests.HTTPError("Unauthorized")
        mock_post.return_value = error_401

        with pytest.raises(requests.HTTPError):
            generate_clip("text", voice_config, "key", output_path)

        assert mock_post.call_count == 1  # no retries

    @patch("dub_chunk.tts.time.sleep")
    @patch("dub_chunk.tts.requests.post")
    def test_raises_after_all_retries_exhausted(self, mock_post, mock_sleep, voice_config, output_path):
        error = MagicMock()
        error.status_code = 503
        error.raise_for_status.side_effect = requests.HTTPError("Service Unavailable")
        mock_post.return_value = error

        with pytest.raises(requests.HTTPError):
            generate_clip("text", voice_config, "key", output_path)

        assert mock_post.call_count == 4  # 1 initial + 3 retries

    @patch("dub_chunk.tts.requests.post")
    def test_creates_parent_directories(self, mock_post, voice_config, tmp_path):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"data"
        mock_post.return_value = mock_response

        deep_path = tmp_path / "sub" / "dir" / "output.mp3"
        generate_clip("text", voice_config, "key", deep_path)
        assert deep_path.exists()

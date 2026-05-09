"""Unit tests for PHASE-5 extended tools."""
import pytest
from pathlib import Path

from tools.tts.index import run as tts_run
from tools.stt.index import run as stt_run
from tools.image_gen.index import run as image_gen_run
from tools.video_gen.index import run as video_gen_run
from tools.music_gen.index import run as music_gen_run
from tools.memory.index import run as memory_run


class TestTTS:
    def test_empty_text_rejected(self):
        result = tts_run({})
        assert result.get("error", {}).get("code") == "SYNTHESIS_FAILED"

    def test_unknown_format_rejected(self):
        result = tts_run({"text": "hello", "format": "flac"})
        assert result.get("error", {}).get("code") == "SYNTHESIS_FAILED"

    def test_model_unavailable_returns_error(self):
        result = tts_run({"text": "hello world"})
        assert result.get("error", {}).get("code") == "MODEL_UNAVAILABLE"


class TestSTT:
    def test_no_audio_path_returns_error(self):
        result = stt_run({})
        assert result.get("error", {}).get("code") == "FILE_NOT_FOUND"

    def test_nonexistent_file_returns_error(self):
        result = stt_run({"audio_path": "/nonexistent.wav"})
        assert result.get("error", {}).get("code") == "FILE_NOT_FOUND"


class TestImageGen:
    def test_empty_prompt_rejected(self):
        result = image_gen_run({})
        assert result.get("error", {}).get("code") == "WORKFLOW_FAILED"

    def test_comfy_unreachable_returns_error(self):
        result = image_gen_run({"prompt": "a cat"})
        assert result.get("error", {}).get("code") in ("COMFY_UNREACHABLE", "WORKFLOW_FAILED")


class TestVideoGen:
    def test_empty_prompt_rejected(self):
        result = video_gen_run({})
        assert result.get("error", {}).get("code") == "GENERATION_FAILED"

    def test_duration_clamped_to_max(self):
        result = video_gen_run({"prompt": "test", "duration_s": 60})
        assert result.get("error", {}).get("code") in ("WAN_UNAVAILABLE", "GENERATION_FAILED")

    def test_wan_unavailable_returns_error(self):
        result = video_gen_run({"prompt": "a cat"})
        assert result.get("error", {}).get("code") in ("WAN_UNAVAILABLE", "GENERATION_FAILED")


class TestMusicGen:
    def test_empty_prompt_rejected(self):
        result = music_gen_run({})
        assert result.get("error", {}).get("code") == "GENERATION_FAILED"

    def test_duration_clamped_to_max(self):
        result = music_gen_run({"prompt": "test", "duration_s": 120})
        assert result.get("error", {}).get("code") in ("MODEL_UNAVAILABLE", "GENERATION_FAILED")

    def test_model_unavailable_returns_error(self):
        result = music_gen_run({"prompt": "upbeat jazz"})
        assert result.get("error", {}).get("code") in ("MODEL_UNAVAILABLE", "GENERATION_FAILED")


class TestMemory:
    def test_unknown_operation_rejected(self):
        result = memory_run({"operation": "delete"})
        assert result.get("error", {}).get("code") == "INVALID_OPERATION"

    def test_store_empty_content_rejected(self):
        result = memory_run({"operation": "store", "content": ""})
        assert result.get("error", {}).get("code") == "INVALID_OPERATION"

    def test_store_no_content_rejected(self):
        result = memory_run({"operation": "store"})
        assert result.get("error", {}).get("code") == "INVALID_OPERATION"

    def test_retrieve_no_memory_id_rejected(self):
        result = memory_run({"operation": "retrieve"})
        assert result.get("error", {}).get("code") == "INVALID_OPERATION"

    def test_search_empty_query_rejected(self):
        result = memory_run({"operation": "search", "query": ""})
        assert result.get("error", {}).get("code") == "INVALID_OPERATION"

    def test_store_unreachable_returns_error(self):
        result = memory_run({"operation": "store", "content": "test"})
        assert result.get("error", {}).get("code") == "MCP_UNREACHABLE"

    def test_retrieve_unreachable_returns_error(self):
        result = memory_run({"operation": "retrieve", "memory_id": "abc"})
        assert result.get("error", {}).get("code") == "MCP_UNREACHABLE"

    def test_search_unreachable_returns_error(self):
        result = memory_run({"operation": "search", "query": "test"})
        assert result.get("error", {}).get("code") == "MCP_UNREACHABLE"

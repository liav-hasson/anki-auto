"""Tests for CLI helper behavior."""

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import AuthenticationError

from anki_auto.cli import (
    DEFAULT_NOTE_MODEL_NAME,
    confirm_run,
    generate_cards,
    main,
    package_cards_with_audio,
    read_input_items,
    resolve_output_path,
)
from anki_auto.config import Settings
from anki_auto.openai_cards import OpenAICardGenerator
from anki_auto.options import AudioOptions
from tests.factories import generated_card

_REQUIRED_ENV_VARS = (
    "OPENAI_API_KEY",
    "ANKI_ORIGIN_LANGUAGE",
    "ANKI_TARGET_LANGUAGE",
    "ANKI_NOTES_LANGUAGE",
    "ANKI_CEFR_LEVEL",
)


def _set_valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Populate a valid set of required environment variables."""

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANKI_ORIGIN_LANGUAGE", "Spanish")
    monkeypatch.setenv("ANKI_TARGET_LANGUAGE", "French")
    monkeypatch.setenv("ANKI_NOTES_LANGUAGE", "English")
    monkeypatch.setenv("ANKI_CEFR_LEVEL", "A2")



def test_read_input_items_ignores_blank_lines_and_comments(tmp_path: Path) -> None:
    """Input files should support comments and blank spacing."""

    input_path = tmp_path / "items.txt"
    input_path.write_text("dog\n\n# skip me\ntrain station\n", encoding="utf-8")

    assert read_input_items(input_path) == ["dog", "train station"]


def test_default_note_model_name_is_v2() -> None:
    """Default imports should use the language-neutral v2 Anki model template."""

    assert DEFAULT_NOTE_MODEL_NAME == "Anki Auto Notes v2"


def test_confirm_run_prints_resolved_output_and_overwrite_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The preflight summary should show the actual output path and overwrite mode."""

    _set_valid_env(monkeypatch)
    monkeypatch.setenv("ANKI_ASSUME_YES", "true")
    monkeypatch.setenv("ANKI_OUTPUT_PATH", str(tmp_path / "deck.apkg"))
    monkeypatch.setenv("ANKI_OVERWRITE_OUTPUT", "false")
    settings = Settings(_env_file=None)
    resolved_output_path = tmp_path / "deck_1.apkg"

    assert confirm_run(settings, 3, output_path=resolved_output_path) is True

    captured = capsys.readouterr()
    assert f"[INFO]   output path:     {resolved_output_path}" in captured.err
    assert "[INFO]   overwrite output: off" in captured.err


def test_package_cards_with_audio_generates_one_file_per_example(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Audio packaging should create one media file for each main sentence."""

    class FakeAudioGenerator:  # pylint: disable=too-few-public-methods
        """Small fake text-to-speech generator that writes the input text."""

        def __init__(
            self,
            model: str,
            voice: str,
            api_key: str | None = None,
            client: object | None = None,
        ) -> None:
            """Store constructor arguments to match the real generator API."""

            self.model = model
            self.voice = voice
            self.api_key = api_key
            self.client = client

        def generate(self, text: str, output_path: Path) -> Path:
            """Write fake audio content and return its path."""

            output_path.write_text(text, encoding="utf-8")
            return output_path

    monkeypatch.setattr("anki_auto.cli.OpenAIAudioGenerator", FakeAudioGenerator)

    packaged_cards = package_cards_with_audio(
        cards=[
            generated_card(
                examples=[
                    {"target": "Le chien court.", "origin": "El perro corre."},
                    {"target": "Le chien dort.", "origin": "El perro duerme."},
                ],
            )
        ],
        generate_audio=True,
        audio=AudioOptions(model="tts-test", voice="voice-test"),
        media_dir=tmp_path,
        concurrency=4,
    )

    assert len(packaged_cards) == 1
    assert len(packaged_cards[0].audio_paths) == 2
    assert packaged_cards[0].audio_paths[0].name.startswith("anki-auto-sleep-1-")
    assert (
        packaged_cards[0].audio_paths[0].read_text(encoding="utf-8")
        == "Le chien court."
    )
    assert packaged_cards[0].audio_paths[1].name.startswith("anki-auto-sleep-2-")
    assert (
        packaged_cards[0].audio_paths[1].read_text(encoding="utf-8")
        == "Le chien dort."
    )


def test_main_missing_required_var_returns_condensed_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing required var yields exit code 1 and one condensed error line."""

    monkeypatch.chdir(tmp_path)
    for name in _REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    exit_code = main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "[ERROR] OPENAI_API_KEY: Field required" in captured.err
    assert captured.err.count("\n") <= len(_REQUIRED_ENV_VARS)


def test_card_generator_threads_api_key_with_injected_client() -> None:
    """The generator accepts an explicit api_key while using an injected client."""

    expected_card = generated_card(source="sleep")
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=expected_card))]
    )
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(parse=lambda **_: completion)
        )
    )
    generator = OpenAICardGenerator(
        prompt_config=SimpleNamespace(
            origin_language="Spanish",
            target_language="French",
            notes_language="English",
            level="A2",
        ),
        api_key="sk-test",
        client=fake_client,
    )

    assert generator.api_key == "sk-test"
    assert generator.generate("sleep") == expected_card


def test_main_invalid_cefr_level_echoes_offending_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An invalid CEFR level is reported with the offending value echoed."""

    monkeypatch.chdir(tmp_path)
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("ANKI_CEFR_LEVEL", "D67")

    exit_code = main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "[ERROR] cefr_level: 'D67' is invalid. Input should be" in captured.err
    assert "Traceback" not in captured.err


def test_main_missing_required_var_omits_value_echo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing required var is reported without a bogus value echo."""

    monkeypatch.chdir(tmp_path)
    _set_valid_env(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    exit_code = main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "[ERROR] OPENAI_API_KEY: Field required" in captured.err
    assert "is invalid" not in captured.err


def test_main_missing_input_file_is_friendly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A nonexistent input path yields a friendly error, not a raw errno."""

    monkeypatch.chdir(tmp_path)
    _set_valid_env(monkeypatch)
    missing = tmp_path / "does-not-exist.txt"
    monkeypatch.setenv("ANKI_INPUT_PATH", str(missing))

    exit_code = main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert (
        f"[ERROR] input file '{missing}' not found. "
        "Create it or set ANKI_INPUT_PATH." in captured.err
    )
    assert "Errno" not in captured.err


def test_main_reports_openai_error_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An upstream OpenAI failure is reported as friendly guidance, exit 1."""

    monkeypatch.chdir(tmp_path)
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("ANKI_ASSUME_YES", "true")
    (tmp_path / "items.txt").write_text("dog\n", encoding="utf-8")

    def _raise(*_args: object, **_kwargs: object) -> None:
        response = httpx.Response(
            401, request=httpx.Request("POST", "https://api.openai.com/v1/chat")
        )
        raise AuthenticationError("bad key", response=response, body=None)

    monkeypatch.setattr("anki_auto.cli.generate_cards", _raise)

    exit_code = main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert (
        "[ERROR] OpenAI authentication failed. Check OPENAI_API_KEY"
        in captured.err
    )
    assert "Traceback" not in captured.err


def test_main_handles_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A Ctrl+C during generation exits cleanly with code 130."""

    monkeypatch.chdir(tmp_path)
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("ANKI_ASSUME_YES", "true")
    (tmp_path / "items.txt").write_text("dog\n", encoding="utf-8")

    def _interrupt(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("anki_auto.cli.generate_cards", _interrupt)

    exit_code = main()

    assert exit_code == 130
    captured = capsys.readouterr()
    assert "[WARNING] Cancelled." in captured.err
    assert "Traceback" not in captured.err


def _settings_with_concurrency(
    monkeypatch: pytest.MonkeyPatch, concurrency: int
) -> Settings:
    """Build a valid Settings object with a given concurrency value."""

    _set_valid_env(monkeypatch)
    monkeypatch.setenv("ANKI_CONCURRENCY", str(concurrency))
    return Settings(_env_file=None)


def test_generate_cards_preserves_input_order_under_scrambled_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Results follow input order even when workers finish out of order."""

    calls: list[str] = []
    lock = threading.Lock()

    class _ScrambledGenerator:  # pylint: disable=too-few-public-methods
        """Fake generator whose later items complete first."""

        def __init__(self, **_kwargs: object) -> None:
            """Ignore the real generator's constructor arguments."""

        def generate(self, item: str) -> object:
            """Sleep inversely to the item index to scramble completion."""

            time.sleep(0.02 * (5 - int(item)))
            with lock:
                calls.append(item)
            return generated_card(source=item)

    monkeypatch.setattr("anki_auto.cli.OpenAICardGenerator", _ScrambledGenerator)
    settings = _settings_with_concurrency(monkeypatch, 5)
    items = ["0", "1", "2", "3", "4"]

    cards = generate_cards(items, settings, client=object())

    assert [card.source for card in cards] == items
    assert sorted(calls) == sorted(items)


def test_generate_cards_concurrency_one_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The degenerate single-worker case still returns cards in input order."""

    class _FakeGenerator:  # pylint: disable=too-few-public-methods
        """Fake generator that echoes the item into the card source."""

        def __init__(self, **_kwargs: object) -> None:
            """Ignore the real generator's constructor arguments."""

        def generate(self, item: str) -> object:
            """Return a card whose source echoes the input item."""

            return generated_card(source=item)

    monkeypatch.setattr("anki_auto.cli.OpenAICardGenerator", _FakeGenerator)
    settings = _settings_with_concurrency(monkeypatch, 1)

    cards = generate_cards(["alpha", "beta"], settings, client=object())

    assert [card.source for card in cards] == ["alpha", "beta"]


def test_main_keyboard_interrupt_from_worker_returns_130(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A Ctrl+C raised inside a worker still exits cleanly with code 130."""

    monkeypatch.chdir(tmp_path)
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("ANKI_ASSUME_YES", "true")
    (tmp_path / "items.txt").write_text("dog\n", encoding="utf-8")

    class _InterruptingGenerator:  # pylint: disable=too-few-public-methods
        """Fake generator whose worker raises KeyboardInterrupt."""

        def __init__(self, **_kwargs: object) -> None:
            """Ignore the real generator's constructor arguments."""

        def generate(self, _item: str) -> object:
            """Simulate a Ctrl+C landing inside a pool worker."""

            raise KeyboardInterrupt

    monkeypatch.setattr("anki_auto.cli.OpenAICardGenerator", _InterruptingGenerator)

    exit_code = main()

    assert exit_code == 130
    captured = capsys.readouterr()
    assert "[WARNING] Cancelled." in captured.err
    assert "Traceback" not in captured.err


def test_resolve_output_path_overwrite_returns_same_path(tmp_path: Path) -> None:
    """With overwrite enabled the existing path is reused in place."""

    path = tmp_path / "deck.apkg"
    path.write_text("x", encoding="utf-8")

    assert resolve_output_path(path, overwrite=True) == path


def test_resolve_output_path_missing_returns_same_path(tmp_path: Path) -> None:
    """A free path is returned unchanged regardless of overwrite."""

    path = tmp_path / "deck.apkg"

    assert resolve_output_path(path, overwrite=False) == path


def test_resolve_output_path_collision_appends_suffix(tmp_path: Path) -> None:
    """An existing path yields the first `_1` variant when not overwriting."""

    path = tmp_path / "deck.apkg"
    path.write_text("x", encoding="utf-8")

    assert resolve_output_path(path, overwrite=False) == tmp_path / "deck_1.apkg"


def test_resolve_output_path_skips_taken_variants(tmp_path: Path) -> None:
    """Already-taken `_1` variants are skipped in favor of the next free name."""

    path = tmp_path / "deck.apkg"
    path.write_text("x", encoding="utf-8")
    (tmp_path / "deck_1.apkg").write_text("x", encoding="utf-8")

    assert resolve_output_path(path, overwrite=False) == tmp_path / "deck_2.apkg"


def _prepare_confirm_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Set up a minimal valid environment for confirm-gate tests."""

    monkeypatch.chdir(tmp_path)
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("ANKI_GENERATE_AUDIO", "false")
    (tmp_path / "items.txt").write_text("dog\n", encoding="utf-8")


def _forbid_generate_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if generation is reached when it should have been gated."""

    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("generate_cards should not be called")

    monkeypatch.setattr("anki_auto.cli.generate_cards", _forbidden)


def _record_generate_cards(monkeypatch: pytest.MonkeyPatch) -> dict[str, bool]:
    """Record whether generation ran and return a single fake card."""

    recorder = {"called": False}

    def _fake(_items: list[str], _settings: object, **_kwargs: object) -> list[object]:
        recorder["called"] = True
        return [generated_card(source="sleep")]

    monkeypatch.setattr("anki_auto.cli.generate_cards", _fake)
    return recorder


def test_confirm_run_assume_yes_proceeds_without_stdin(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ANKI_ASSUME_YES proceeds without touching stdin."""

    _prepare_confirm_run(monkeypatch, tmp_path)
    monkeypatch.setenv("ANKI_ASSUME_YES", "true")

    def _explode() -> bool:
        raise AssertionError("stdin.isatty must not be consulted")

    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=_explode))
    recorder = _record_generate_cards(monkeypatch)

    exit_code = main()

    assert exit_code == 0
    assert recorder["called"] is True


def test_confirm_run_non_tty_fails_with_guidance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-interactive terminal without assume_yes fails with exit code 1."""

    _prepare_confirm_run(monkeypatch, tmp_path)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: False))
    _forbid_generate_cards(monkeypatch)

    exit_code = main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert (
        "[ERROR] Confirmation required but no interactive terminal is available"
        in captured.err
    )
    assert "ANKI_ASSUME_YES=true" in captured.err


def test_confirm_run_interactive_yes_proceeds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An interactive `y` reply proceeds with generation."""

    _prepare_confirm_run(monkeypatch, tmp_path)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    recorder = _record_generate_cards(monkeypatch)

    exit_code = main()

    assert exit_code == 0
    assert recorder["called"] is True


def test_confirm_run_interactive_empty_declines(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An empty interactive reply declines and never generates."""

    _prepare_confirm_run(monkeypatch, tmp_path)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    _forbid_generate_cards(monkeypatch)

    exit_code = main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[WARNING] Aborted by user." in captured.err

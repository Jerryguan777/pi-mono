"""Tests for pi_coding_agent.main."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pi_coding_agent.main import (
    _get_package_command_usage,
    _handle_package_command,
    _parse_package_command,
    _prepare_initial_message,
    _print_package_command_help,
    main,
)

# ---------------------------------------------------------------------------
# _get_package_command_usage
# ---------------------------------------------------------------------------


def test_get_package_command_usage_install() -> None:
    result = _get_package_command_usage("install")
    assert "install" in result
    assert "<source>" in result


def test_get_package_command_usage_remove() -> None:
    result = _get_package_command_usage("remove")
    assert "remove" in result


def test_get_package_command_usage_update() -> None:
    result = _get_package_command_usage("update")
    assert "update" in result


def test_get_package_command_usage_list() -> None:
    result = _get_package_command_usage("list")
    assert "list" in result


def test_get_package_command_usage_unknown() -> None:
    result = _get_package_command_usage("unknown-cmd")
    assert "unknown-cmd" in result


# ---------------------------------------------------------------------------
# _print_package_command_help
# ---------------------------------------------------------------------------


def test_print_package_command_help_install(capsys: pytest.CaptureFixture[str]) -> None:
    _print_package_command_help("install")
    captured = capsys.readouterr()
    assert "install" in captured.out.lower()


def test_print_package_command_help_remove(capsys: pytest.CaptureFixture[str]) -> None:
    _print_package_command_help("remove")
    captured = capsys.readouterr()
    assert "remove" in captured.out.lower()


def test_print_package_command_help_update(capsys: pytest.CaptureFixture[str]) -> None:
    _print_package_command_help("update")
    captured = capsys.readouterr()
    assert "update" in captured.out.lower()


def test_print_package_command_help_list(capsys: pytest.CaptureFixture[str]) -> None:
    _print_package_command_help("list")
    captured = capsys.readouterr()
    assert "list" in captured.out.lower()


# ---------------------------------------------------------------------------
# _parse_package_command
# ---------------------------------------------------------------------------


def test_parse_package_command_not_a_command() -> None:
    result = _parse_package_command(["--help"])
    assert result is None


def test_parse_package_command_empty() -> None:
    result = _parse_package_command([])
    assert result is None


def test_parse_package_command_install() -> None:
    result = _parse_package_command(["install", "npm:@foo/bar"])
    assert result is not None
    assert result["command"] == "install"
    assert result["source"] == "npm:@foo/bar"
    assert result["local"] is False
    assert result["help"] is False


def test_parse_package_command_install_local() -> None:
    result = _parse_package_command(["install", "npm:@foo/bar", "-l"])
    assert result is not None
    assert result["local"] is True


def test_parse_package_command_install_help() -> None:
    result = _parse_package_command(["install", "--help"])
    assert result is not None
    assert result["help"] is True


def test_parse_package_command_remove() -> None:
    result = _parse_package_command(["remove", "npm:@foo/bar"])
    assert result is not None
    assert result["command"] == "remove"
    assert result["source"] == "npm:@foo/bar"


def test_parse_package_command_update_no_source() -> None:
    result = _parse_package_command(["update"])
    assert result is not None
    assert result["command"] == "update"
    assert result["source"] is None


def test_parse_package_command_update_with_source() -> None:
    result = _parse_package_command(["update", "npm:@foo/bar"])
    assert result is not None
    assert result["source"] == "npm:@foo/bar"


def test_parse_package_command_list() -> None:
    result = _parse_package_command(["list"])
    assert result is not None
    assert result["command"] == "list"


def test_parse_package_command_invalid_option_for_update() -> None:
    result = _parse_package_command(["update", "-l"])
    assert result is not None
    assert result["invalid_option"] == "-l"


def test_parse_package_command_unknown_flag() -> None:
    result = _parse_package_command(["install", "--unknown"])
    assert result is not None
    assert result["invalid_option"] == "--unknown"


# ---------------------------------------------------------------------------
# _handle_package_command
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_package_command_not_a_command() -> None:
    result = await _handle_package_command(["--help"])
    assert result is False


@pytest.mark.asyncio
async def test_handle_package_command_install_help(capsys: pytest.CaptureFixture[str]) -> None:
    result = await _handle_package_command(["install", "--help"])
    assert result is True
    captured = capsys.readouterr()
    assert "install" in captured.out.lower()


@pytest.mark.asyncio
async def test_handle_package_command_install_no_source() -> None:
    with pytest.raises(SystemExit) as exc_info:
        await _handle_package_command(["install"])
    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_handle_package_command_invalid_option() -> None:
    with pytest.raises(SystemExit) as exc_info:
        await _handle_package_command(["install", "--bad-flag"])
    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_handle_package_command_install(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import sys
    from unittest.mock import AsyncMock, MagicMock

    main_mod = sys.modules["pi_coding_agent.main"]

    mock_pm = MagicMock()
    mock_pm.install = AsyncMock()
    mock_pm.add_source_to_settings = MagicMock(return_value=True)
    mock_pm.set_progress_callback = MagicMock()

    monkeypatch.setattr(
        "pi_coding_agent.core.package_manager.DefaultPackageManager", lambda opts: mock_pm,
    )
    monkeypatch.setattr(main_mod, "SettingsManager", MagicMock(create=MagicMock(return_value=MagicMock())))
    monkeypatch.chdir(tmp_path)

    result = await _handle_package_command(["install", "npm:@foo/bar"])
    assert result is True
    mock_pm.install.assert_awaited_once()
    captured = capsys.readouterr()
    assert "Installed" in captured.out


@pytest.mark.asyncio
async def test_handle_package_command_list_empty(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import sys
    from unittest.mock import MagicMock

    main_mod = sys.modules["pi_coding_agent.main"]

    mock_sm = MagicMock()
    mock_sm._global_settings = MagicMock()
    mock_sm._global_settings.packages = []
    mock_sm._project_settings = MagicMock()
    mock_sm._project_settings.packages = []

    monkeypatch.setattr(
        "pi_coding_agent.core.package_manager.DefaultPackageManager", lambda opts: MagicMock(),
    )
    monkeypatch.setattr(main_mod, "SettingsManager", MagicMock(create=MagicMock(return_value=mock_sm)))
    monkeypatch.chdir(tmp_path)

    result = await _handle_package_command(["list"])
    assert result is True
    captured = capsys.readouterr()
    assert "No packages installed" in captured.out


@pytest.mark.asyncio
async def test_handle_package_command_update(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import sys
    from unittest.mock import AsyncMock, MagicMock

    main_mod = sys.modules["pi_coding_agent.main"]

    mock_pm = MagicMock()
    mock_pm.update = AsyncMock()
    mock_pm.set_progress_callback = MagicMock()

    monkeypatch.setattr(
        "pi_coding_agent.core.package_manager.DefaultPackageManager", lambda opts: mock_pm,
    )
    monkeypatch.setattr(main_mod, "SettingsManager", MagicMock(create=MagicMock(return_value=MagicMock())))
    monkeypatch.chdir(tmp_path)

    result = await _handle_package_command(["update"])
    assert result is True
    mock_pm.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_package_command_remove(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import sys
    from unittest.mock import AsyncMock, MagicMock

    main_mod = sys.modules["pi_coding_agent.main"]

    mock_pm = MagicMock()
    mock_pm.remove = AsyncMock()
    mock_pm.remove_source_from_settings = MagicMock(return_value=True)
    mock_pm.set_progress_callback = MagicMock()

    monkeypatch.setattr(
        "pi_coding_agent.core.package_manager.DefaultPackageManager", lambda opts: mock_pm,
    )
    monkeypatch.setattr(main_mod, "SettingsManager", MagicMock(create=MagicMock(return_value=MagicMock())))
    monkeypatch.chdir(tmp_path)

    result = await _handle_package_command(["remove", "npm:@foo/bar"])
    assert result is True
    mock_pm.remove.assert_awaited_once()
    captured = capsys.readouterr()
    assert "Removed" in captured.out


# ---------------------------------------------------------------------------
# _prepare_initial_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_initial_message_no_files() -> None:
    msg, images, remaining = await _prepare_initial_message([], ["Hello"])
    assert msg is None
    assert images is None
    assert remaining == ["Hello"]


@pytest.mark.asyncio
async def test_prepare_initial_message_with_file(tmp_path: pytest.TempdirFactory) -> None:
    from pathlib import Path

    f = Path(str(tmp_path)) / "test.txt"
    f.write_text("content", encoding="utf-8")

    msg, _images, remaining = await _prepare_initial_message([str(f)], ["Hello"])
    assert msg is not None
    assert "content" in msg
    assert "Hello" in msg
    assert remaining == []


# ---------------------------------------------------------------------------
# main - version and help
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_main_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        await main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() != ""


@pytest.mark.asyncio
async def test_main_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        await main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Usage" in captured.out


@pytest.mark.asyncio
async def test_main_list_models(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("pi_coding_agent.main.run_migrations") as mock_mig:
        mock_mig.return_value = MagicMock(migrated_auth_providers=[], deprecation_warnings=[])
        with pytest.raises(SystemExit) as exc_info:
            await main(["--list-models"])
    assert exc_info.value.code == 0


@pytest.mark.asyncio
async def test_main_export_stub(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("pi_coding_agent.main.run_migrations") as mock_mig:
        mock_mig.return_value = MagicMock(migrated_auth_providers=[], deprecation_warnings=[])
        with (
            patch("pi_coding_agent.main._read_piped_stdin", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            await main(["--export", "session.jsonl"])
    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_main_rpc_with_file_args_exits(capsys: pytest.CaptureFixture[str]) -> None:
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"content")
        fname = f.name

    with patch("pi_coding_agent.main.run_migrations") as mock_mig:
        mock_mig.return_value = MagicMock(migrated_auth_providers=[], deprecation_warnings=[])
        with pytest.raises(SystemExit) as exc_info:
            await main(["--mode", "rpc", f"@{fname}"])
    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_main_print_mode_exits(capsys: pytest.CaptureFixture[str]) -> None:
    mock_session = MagicMock()
    mock_session.model = MagicMock()  # non-None so it doesn't exit with "No models"
    mock_result = MagicMock(session=mock_session, model_fallback_message=None)

    with patch("pi_coding_agent.main.run_migrations") as mock_mig:
        mock_mig.return_value = MagicMock(migrated_auth_providers=[], deprecation_warnings=[])
        with (
            patch("pi_coding_agent.main._read_piped_stdin", return_value=None),
            patch("pi_coding_agent.main.create_agent_session", return_value=mock_result),
            patch("pi_coding_agent.main.run_print_mode", return_value=None) as mock_print,
            pytest.raises(SystemExit) as exc_info,
        ):
            await main(["--print", "Hello world"])
    assert exc_info.value.code == 0
    mock_print.assert_called_once()


@pytest.mark.asyncio
async def test_main_package_install_handled(capsys: pytest.CaptureFixture[str]) -> None:
    # install command is handled before running migrations
    result_called: list[bool] = []

    async def fake_migrations_check(a: list[str]) -> bool:
        result_called.append(True)
        return True

    with patch("pi_coding_agent.main._handle_package_command", side_effect=fake_migrations_check):
        await main(["install", "npm:@foo/bar"])

    assert result_called

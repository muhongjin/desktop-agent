import pytest

from desktop_agent.tools.powershell import ShellUnavailable, select_shell


def test_auto_prefers_pwsh(monkeypatch):
    found = {"pwsh.exe": "C:/PowerShell/7/pwsh.exe", "powershell.exe": "C:/Windows/powershell.exe"}
    monkeypatch.setattr("desktop_agent.tools.powershell.shutil.which", found.get)
    assert select_shell("auto") == "C:/PowerShell/7/pwsh.exe"


def test_auto_falls_back_to_windows_powershell(monkeypatch):
    found = {"powershell.exe": "C:/Windows/powershell.exe"}
    monkeypatch.setattr("desktop_agent.tools.powershell.shutil.which", found.get)
    assert select_shell("auto") == "C:/Windows/powershell.exe"


def test_explicit_mode_overrides_auto_detection(monkeypatch):
    found = {"pwsh.exe": "C:/PowerShell/7/pwsh.exe", "powershell.exe": "C:/Windows/powershell.exe"}
    monkeypatch.setattr("desktop_agent.tools.powershell.shutil.which", found.get)
    assert select_shell("windows-powershell") == "C:/Windows/powershell.exe"


def test_missing_shell_has_readable_error(monkeypatch):
    monkeypatch.setattr("desktop_agent.tools.powershell.shutil.which", lambda name: None)
    with pytest.raises(ShellUnavailable, match="auto"):
        select_shell()

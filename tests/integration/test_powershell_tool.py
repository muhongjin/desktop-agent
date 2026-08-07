import asyncio
import sys

import pytest

from desktop_agent.tools.powershell import PowerShellExecutor, ShellUnavailable

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Objects are required")


@pytest.mark.asyncio
async def test_powershell_captures_stdout_and_exit_code():
    try:
        executor = PowerShellExecutor("auto")
    except ShellUnavailable:
        pytest.skip("PowerShell is not installed")
    result = await executor.execute("Write-Output 'desktop-agent-test'")
    assert "desktop-agent-test" in result.stdout
    assert result.exit_code == 0
    assert result.cancelled is False


@pytest.mark.asyncio
async def test_stop_terminates_job_object_process_tree():
    try:
        executor = PowerShellExecutor("auto")
    except ShellUnavailable:
        pytest.skip("PowerShell is not installed")
    stop = asyncio.Event()
    task = asyncio.create_task(executor.execute("Start-Sleep -Seconds 30", stop_event=stop))
    await asyncio.sleep(0.3)
    stop.set()
    result = await asyncio.wait_for(task, timeout=5)
    assert result.cancelled is True

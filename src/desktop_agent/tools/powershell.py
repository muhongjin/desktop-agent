import asyncio
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class ShellUnavailable(Exception):
    pass


def select_shell(mode: str = "auto") -> str:
    choices = {
        "pwsh": ("pwsh.exe", "pwsh"),
        "windows-powershell": ("powershell.exe", "powershell"),
    }
    if mode == "auto":
        ordered = ("pwsh.exe", "pwsh", "powershell.exe", "powershell")
    elif mode in choices:
        ordered = choices[mode]
    else:
        raise ValueError(f"Unknown shell mode: {mode}")
    for executable in ordered:
        found = shutil.which(executable)
        if found:
            return found
    raise ShellUnavailable(f"No executable found for shell mode: {mode}")


@dataclass(frozen=True, slots=True)
class ShellResult:
    stdout: str
    stderr: str
    exit_code: int
    shell: str
    cancelled: bool = False


class PowerShellExecutor:
    def __init__(self, mode: str = "auto"):
        self.shell = select_shell(mode)
        self._process: subprocess.Popen[bytes] | None = None
        self._job = None

    async def execute(
        self,
        command: str,
        *,
        cwd: str | Path | None = None,
        stop_event: asyncio.Event | None = None,
    ) -> ShellResult:
        if self._process is not None:
            raise RuntimeError("A PowerShell command is already running")
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        process = await asyncio.to_thread(
            subprocess.Popen,
            [self.shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creation_flags,
        )
        self._process = process
        if sys.platform == "win32":
            try:
                self._job = self._create_job(process.pid)
            except BaseException:
                process.terminate()
                await asyncio.to_thread(process.communicate)
                self._process = None
                raise
        communication = asyncio.create_task(asyncio.to_thread(process.communicate))
        stop_waiter = asyncio.create_task(stop_event.wait()) if stop_event is not None else None
        cancelled = False
        try:
            if stop_waiter is None:
                stdout, stderr = await communication
            else:
                done, _ = await asyncio.wait({communication, stop_waiter}, return_when=asyncio.FIRST_COMPLETED)
                if stop_waiter in done and stop_event.is_set() and not communication.done():
                    cancelled = True
                    self.stop()
                stdout, stderr = await communication
        finally:
            if stop_waiter is not None:
                stop_waiter.cancel()
            self._close_job()
            self._process = None
        return ShellResult(
            stdout=self._decode(stdout),
            stderr=self._decode(stderr),
            exit_code=process.returncode,
            shell=self.shell,
            cancelled=cancelled,
        )

    def stop(self) -> None:
        if self._job is not None:
            self._close_job()
        elif self._process is not None and self._process.poll() is None:
            self._process.terminate()

    def close(self) -> None:
        self.stop()

    def _create_job(self, process_id: int):
        import win32api
        import win32con
        import win32job

        job = win32job.CreateJobObject(None, "")
        information = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        information["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, information)
        access = win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE
        process_handle = win32api.OpenProcess(access, False, process_id)
        try:
            win32job.AssignProcessToJobObject(job, process_handle)
        except BaseException:
            win32api.CloseHandle(job)
            raise
        finally:
            win32api.CloseHandle(process_handle)
        return job

    def _close_job(self) -> None:
        if self._job is None:
            return
        import win32api

        win32api.CloseHandle(self._job)
        self._job = None

    def _decode(self, value: bytes) -> str:
        for encoding in ("utf-8", "gb18030"):
            try:
                return value.decode(encoding)
            except UnicodeDecodeError:
                continue
        return value.decode(errors="replace")

import sys
import threading
from PyQt6.QtCore import QObject, pyqtSignal

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    try:
        from winpty import PtyProcess
    except ImportError:
        raise ImportError("Run: pip install pywinpty")
else:
    import os, pty, select, signal


def _get_short_path(long_path):
    import ctypes
    buf = ctypes.create_unicode_buffer(32768)
    ctypes.windll.kernel32.GetShortPathNameW(long_path, buf, 32768)
    return buf.value or long_path


def _find_python_with_ofscraper():
    """Find a Python interpreter that has ofscraper installed."""
    import shutil, subprocess, os
    
    candidates = []
    
    # 1. Try PATH pythons
    for py in ['python', 'python3', 'py']:
        found = shutil.which(py)
        if found:
            candidates.append(found)
    
    # 2. Try common locations
    home = os.path.expanduser('~')
    common = [
        os.path.join(home, 'AppData', 'Local', 'Programs', 'Python'),
        os.path.join(home, 'AppData', 'Roaming', 'Python'),
        r'C:\Python311', r'C:\Python312', r'C:\Python310',
    ]
    for base in common:
        if os.path.isdir(base):
            for item in os.listdir(base):
                exe = os.path.join(base, item, 'python.exe')
                if os.path.exists(exe):
                    candidates.append(exe)
    
    # 3. Test each candidate
    for candidate in candidates:
        try:
            result = subprocess.run(
                [candidate, '-c', 'import ofscraper; print("ok")'],
                capture_output=True, text=True, timeout=5
            )
            if 'ok' in result.stdout:
                return _get_short_path(candidate)
        except Exception:
            continue
    
    return None


def _build_windows_cmd(command):
    if getattr(sys, 'frozen', False):
        python = _find_python_with_ofscraper()
        if python:
            return " ".join([python, "-m", "ofscraper"] + command[1:])
        # Fallback error
        return (
            'cmd /c echo [ERROR] Could not find Python with ofscraper installed. '
            'Make sure Python is in your PATH and ofscraper is installed. && pause'
        )
    exe = _get_short_path(sys.executable)
    return " ".join([exe, "-m", "ofscraper"] + command[1:])


class _WindowsRunner(QObject):
    output_received = pyqtSignal(str)
    process_ended   = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self._proc = self.pid = None
        self._running = False

    def start(self, command):
        self._proc    = PtyProcess.spawn(_build_windows_cmd(command))
        self.pid      = self._proc.pid
        self._running = True
        threading.Thread(target=self._read_loop, daemon=True).start()

    def _read_loop(self):
            while self._running:
                try:
                    data = self._proc.read(4096)
                    if data:
                        self.output_received.emit(data)
                except Exception as e:
                    self.output_received.emit(f'\r\n[RUNNER ERROR] {e}\r\n')
                    break
            exit_code = 0
            try:
                exit_code = self._proc.exitstatus or 0
            except Exception:
                pass
            self.process_ended.emit(exit_code)

    def write(self, text):
        if self._proc:
            self._proc.write(text)

    def resize(self, rows, cols=80):
        if self._proc:
            try:
                self._proc.setwinsize(rows, cols)
            except Exception:
                pass

    def stop(self):
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass


class _UnixRunner(QObject):
    output_received = pyqtSignal(str)
    process_ended   = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.master_fd = self.pid = None
        self._running = False

    def start(self, command):
        self.pid, self.master_fd = pty.fork()
        if self.pid == 0:
            os.execvp(command[0], command)
        else:
            self._running = True
            threading.Thread(target=self._read_loop, daemon=True).start()

    def _read_loop(self):
        while self._running:
            try:
                r, _, _ = select.select([self.master_fd], [], [], 0.05)
                if r:
                    self.output_received.emit(
                        os.read(self.master_fd, 4096).decode("utf-8", errors="replace"))
            except OSError:
                break
        self.process_ended.emit(0)

    def write(self, text):
        if self.master_fd is not None:
            os.write(self.master_fd, text.encode())

    def resize(self, rows, cols=80):
        if self.master_fd is not None:
            try:
                import fcntl, termios, struct
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ,
                            struct.pack('HHHH', rows, cols, 0, 0))
            except Exception:
                pass

    def stop(self):
        self._running = False
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


ProcessRunner = _WindowsRunner if IS_WINDOWS else _UnixRunner
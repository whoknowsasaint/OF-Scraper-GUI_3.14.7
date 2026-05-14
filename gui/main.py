import sys
import re
import shlex
import os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLineEdit, QPushButton, QLabel, QTextEdit, QStatusBar,
    QStackedWidget, QScrollArea, QFrame, QCheckBox, QSpinBox, QFileDialog,
)
from PyQt6.QtCore  import Qt, QSettings, QTimer, pyqtSlot
from PyQt6.QtGui   import QFont, QKeySequence, QShortcut, QIcon

from gui.terminal_display import TerminalDisplay
from gui.process_runner   import ProcessRunner
from gui.prompt_handler   import PromptHandler

UP          = '\x1b[A'
DOWN        = '\x1b[B'
ENTER       = '\r'
SHIFT_RIGHT = '\x1b[1;2C'
PAGEDOWN    = '\x1b[6~'

_ANSI_STRIP = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\[\?[0-9]+[hl]|\x1b[=>]')
_DL_USER_RE = re.compile(r'Performing Downloading Action on ([\w\-\.]+)')
_DL_PATH_RE = re.compile(r'Saving files to ([^\n\|{]+)')
_DL_PROG_RE = re.compile(
    r'Download Progress:.*?(\d+) photos.*?(\d+) videos.*?(\d+) audios'
    r'.*?(\d+) skipped.*?(\d+) failed', re.DOTALL)


def navigate_to(runner, target_idx, current_idx=0):
    delta = target_idx - current_idx
    if delta > 0:
        runner.write(DOWN * delta + ENTER)
    elif delta < 0:
        runner.write(UP * abs(delta) + ENTER)
    else:
        runner.write(ENTER)


def select_checkboxes(runner, all_choices, selected):
    keys = ''
    current = 0
    for idx, choice in enumerate(all_choices):
        if choice in selected:
            keys += DOWN * (idx - current) + SHIFT_RIGHT
            current = idx
    runner.write(keys + ENTER)


# ── Stylesheet ────────────────────────────────────────────────────────────────

DARK_STYLE = """
    QMainWindow, QWidget { background:#0d1117; color:#c9d1d9; }
    QSplitter::handle    { background:#1f6feb; width:2px; }
    #launcher_bar  { background:#161b22; border-bottom:2px solid #21262d; }
    #input_bar     { background:#161b22; border-top:1px solid #21262d; }
    #side_panel    { background:#161b22; border-left:2px solid #1f6feb; }
    #panel_header  { background:#0a0f14; border-bottom:2px solid #1f6feb; padding:14px 16px; }
    #panel_title   { color:#e6edf3; font-family:'Segoe UI',Arial,sans-serif; font-size:13pt; font-weight:bold; }
    #panel_subtitle{ color:#8b949e; font-size:9pt; margin-top:2px; }
    #panel_idle    { color:#484f58; font-size:11pt; font-style:italic; }
    #prompt_label  { color:#ffd54f; font-size:11pt; font-weight:bold; }
    #field_label   { color:#8b949e; font-size:9pt; }
    #args_input, #raw_input, #prompt_input, #search_input, #path_input, #list_fallback {
        background:#0d1117; border:1px solid #30363d; border-radius:6px;
        color:#c9d1d9; font-family:'Courier New'; font-size:10pt; padding:5px 10px;
        min-height:28px;
    }
    #args_input:focus, #raw_input:focus, #prompt_input:focus,
    #search_input:focus, #path_input:focus { border-color:#388bfd; }
    #list_fallback { border:1px solid #e3b341; }
    #list_fallback:focus { border-color:#ffd54f; }
    #prompt_textarea {
        background:#0d1117; border:1px solid #30363d; border-radius:6px;
        color:#c9d1d9; font-family:'Courier New'; font-size:10pt; padding:6px 10px;
    }
    #choice_btn {
        background:#0d1117; border:1px solid #21262d; border-left:3px solid #1f6feb;
        border-radius:6px; color:#c9d1d9;
        font-family:'Segoe UI',Arial,sans-serif; font-size:11pt;
        padding:10px 16px; text-align:left; margin-bottom:2px;
    }
    #choice_btn:hover  { background:#1c2a3d; border-color:#388bfd; color:#79c0ff; }
    #choice_btn:pressed{ background:#1f6feb; color:#fff; }
    QCheckBox {
        color:#c9d1d9; font-family:'Segoe UI',Arial,sans-serif;
        font-size:11pt; spacing:10px; padding:5px 0;
    }
    QCheckBox::indicator {
        width:18px; height:18px; border-radius:4px;
        border:2px solid #30363d; background:#0d1117;
    }
    QCheckBox::indicator:checked { background:#2ea043; border-color:#2ea043; }
    QCheckBox::indicator:hover   { border-color:#388bfd; }
    QSpinBox {
        background:#0d1117; border:1px solid #30363d; border-radius:6px;
        color:#c9d1d9; font-family:'Courier New'; font-size:12pt;
        padding:5px 10px; min-height:36px;
    }
    QSpinBox:focus { border-color:#388bfd; }
    QSpinBox::up-button, QSpinBox::down-button {
        width:24px; background:#21262d; border:none; border-radius:3px;
    }
    QPushButton {
        background:#21262d; border:1px solid #30363d; border-radius:6px;
        color:#c9d1d9; padding:7px 16px; font-size:10pt;
        font-family:'Segoe UI',Arial,sans-serif;
    }
    QPushButton:hover   { background:#30363d; }
    QPushButton:pressed { background:#1f6feb; border-color:#388bfd; }
    QPushButton#btn_yes {
        background:#1a3a1a; border:2px solid #2ea043; color:#69f0ae;
        font-size:13pt; font-weight:bold; padding:12px 0; border-radius:8px;
    }
    QPushButton#btn_yes:hover { background:#1f4a1f; }
    QPushButton#btn_no {
        background:#3d1f1f; border:2px solid #da3633; color:#ef9a9a;
        font-size:13pt; font-weight:bold; padding:12px 0; border-radius:8px;
    }
    QPushButton#btn_no:hover { background:#4d2828; }
    QPushButton#btn_confirm, QPushButton#btn_send {
        background:#1a3a1a; border:1px solid #2ea043; color:#69f0ae;
        font-size:11pt; font-weight:bold; padding:9px 0; border-radius:6px;
    }
    QPushButton#btn_confirm:hover, QPushButton#btn_send:hover { background:#1f4a1f; }
    QPushButton#btn_confirm:disabled { background:#161b22; color:#484f58; border-color:#30363d; }
    QPushButton#btn_launch {
        background:#1a3a1a; border:1px solid #2ea043; color:#69f0ae;
        font-weight:bold; padding:5px 20px; border-radius:6px;
    }
    QPushButton#btn_launch:hover    { background:#1f4a1f; }
    QPushButton#btn_launch:disabled { background:#161b22; color:#484f58; border-color:#30363d; }
    QPushButton#btn_stop {
        background:#3d1f1f; border:1px solid #da3633; color:#ef9a9a; border-radius:6px;
    }
    QPushButton#btn_stop:hover    { background:#4d2828; }
    QPushButton#btn_stop:disabled { background:#161b22; color:#484f58; border-color:#30363d; }
    QPushButton#btn_restart {
        background:#1a2a3a; border:1px solid #388bfd; color:#79c0ff;
        padding:5px 14px; border-radius:6px;
    }
    QPushButton#btn_restart:hover    { background:#1f3550; }
    QPushButton#btn_restart:disabled { background:#161b22; color:#484f58; border-color:#30363d; }
    QPushButton#btn_dismiss {
        background:#161b22; border:2px solid #388bfd; color:#79c0ff;
        font-size:11pt; padding:9px 0; border-radius:6px;
    }
    QPushButton#btn_dismiss:hover { background:#1c2a3d; }
    QPushButton#btn_browse { background:#21262d; border:1px solid #388bfd; color:#79c0ff; padding:5px 12px; }
    QPushButton#btn_select_all, QPushButton#btn_deselect_all { padding:4px 12px; font-size:9pt; }
    QStatusBar { background:#010409; color:#484f58; font-size:9pt; padding:3px 10px; }
    QScrollBar:vertical  { background:#0d1117; width:8px; border-radius:4px; }
    QScrollBar::handle:vertical { background:#30363d; border-radius:4px; min-height:24px; }
    QScrollBar::handle:vertical:hover { background:#484f58; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
    QScrollBar:horizontal { height:0px; }
"""


# ── Download Progress Widget ──────────────────────────────────────────────────

class DownloadProgressWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        lbl = QLabel('Downloading')
        lbl.setObjectName('field_label')
        root.addWidget(lbl)

        self._user = QLabel('...')
        self._user.setObjectName('panel_title')
        root.addWidget(self._user)

        root.addWidget(self._sep())

        path_lbl = QLabel('Saving to:')
        path_lbl.setObjectName('field_label')
        root.addWidget(path_lbl)

        self._path = QLabel('...')
        self._path.setWordWrap(True)
        self._path.setStyleSheet(
            'color:#69f0ae; font-size:9pt; font-family:Courier New;')
        root.addWidget(self._path)

        root.addWidget(self._sep())

        self._photos  = QLabel('📷  0 photos')
        self._photos.setStyleSheet('color:#79c0ff; font-size:12pt;')
        self._videos  = QLabel('🎬  0 videos')
        self._videos.setStyleSheet('color:#c792ea; font-size:12pt;')
        self._audios  = QLabel('🎵  0 audios')
        self._audios.setStyleSheet('color:#ffd54f; font-size:12pt;')
        self._skipped = QLabel('⏭  0 skipped   ✗  0 failed')
        self._skipped.setObjectName('field_label')
        for w in (self._photos, self._videos, self._audios, self._skipped):
            root.addWidget(w)

        root.addStretch()

    @staticmethod
    def _sep():
        l = QLabel('─' * 28)
        l.setStyleSheet('color:#21262d;')
        return l

    def set_user(self, username):
        self._user.setText(username)

    def set_path(self, path):
        p = path.replace('\\', '/').rstrip('/')
        parts = p.split('/')
        short = '/'.join(parts[:6]) + '/...' if len(parts) > 6 else p
        if len(short) > 50:
            short = '...' + short[-47:]
        self._path.setText(short)

    def update_stats(self, photos, videos, audios, skipped, failed):
        self._photos.setText(f'📷  {photos} photos')
        self._videos.setText(f'🎬  {videos} videos')
        self._audios.setText(f'🎵  {audios} audios')
        self._skipped.setText(f'⏭  {skipped} skipped   ✗  {failed} failed')


# ── Model Selector Widget ─────────────────────────────────────────────────────

class ModelSelectWidget(QWidget):
    def __init__(self, runner, handler, parent=None):
        super().__init__(parent)
        self.runner   = runner
        self.handler  = handler
        self._on_done = None
        self._all_models = []

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        info = QLabel('Click a model to scrape it.\nGUI filter stays local.')
        info.setObjectName('field_label')
        info.setWordWrap(True)
        root.addWidget(info)

        self._search = QLineEdit()
        self._search.setObjectName('search_input')
        self._search.setPlaceholderText('Filter list...')
        self._search.textChanged.connect(self._filter_display)
        root.addWidget(self._search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._bc = QWidget()
        self._bl = QVBoxLayout(self._bc)
        self._bl.setContentsMargins(0, 0, 0, 0)
        self._bl.setSpacing(4)
        self._bl.addStretch()
        scroll.setWidget(self._bc)
        root.addWidget(scroll, stretch=1)

        self._status = QLabel('Waiting for model list...')
        self._status.setObjectName('field_label')
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status)

    def load(self, models, on_done):
        self._on_done    = on_done
        self._all_models = models
        self._search.clear()
        self._render(models)

    def _render(self, models):
        while self._bl.count() > 1:
            item = self._bl.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if models:
            self._status.hide()
            for username in models:
                btn = QPushButton(f'  {username}')
                btn.setObjectName('choice_btn')
                btn.clicked.connect(lambda _, u=username: self._select(u))
                self._bl.insertWidget(self._bl.count() - 1, btn)
        else:
            self._status.setText('No models matched.')
            self._status.show()

    def _filter_display(self, text):
        filtered = [m for m in self._all_models
                    if text.lower() in m.lower()] if text else self._all_models
        self._render(filtered)

    def _select(self, username):
        # Type username to filter fuzzy to one result, pagedown to toggle, enter to confirm
        self.runner.write(username)
        QTimer.singleShot(500, lambda: self._toggle_confirm())

    def _toggle_confirm(self):
        self.runner.write(PAGEDOWN + ENTER)
        self.handler.clear()
        if self._on_done:
            self._on_done()


# ── Filepath Widget ───────────────────────────────────────────────────────────

class FilepathWidget(QWidget):
    def __init__(self, runner, handler, parent=None):
        super().__init__(parent)
        self.runner = runner; self.handler = handler
        self._on_done = None; self._dir_only = False
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14); root.setSpacing(10)
        self._label = QLabel(); self._label.setObjectName('field_label')
        self._label.setWordWrap(True); root.addWidget(self._label)
        row = QHBoxLayout()
        self._path_input = QLineEdit(); self._path_input.setObjectName('path_input')
        self._path_input.setPlaceholderText('Click Browse or type path...')
        row.addWidget(self._path_input, stretch=1)
        browse = QPushButton('Browse'); browse.setObjectName('btn_browse')
        browse.clicked.connect(self._browse); row.addWidget(browse)
        root.addLayout(row)
        send = QPushButton('Send'); send.setObjectName('btn_send')
        send.clicked.connect(self._send); root.addWidget(send)
        root.addStretch()

    def load(self, label, dir_only, on_done):
        self._label.setText(label); self._dir_only = dir_only
        self._on_done = on_done; self._path_input.clear()

    def _browse(self):
        path = (QFileDialog.getExistingDirectory(self, 'Select folder')
                if self._dir_only else QFileDialog.getOpenFileName(self, 'Select file')[0])
        if path:
            self._path_input.setText(path)

    def _send(self):
        path = self._path_input.text().strip()
        if path:
            self.runner.write(path + ENTER); self.handler.clear()
            if self._on_done: self._on_done()


# ── Spinbox Widget ────────────────────────────────────────────────────────────

class SpinboxWidget(QWidget):
    def __init__(self, runner, handler, parent=None):
        super().__init__(parent)
        self.runner = runner; self.handler = handler; self._on_done = None
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14); root.setSpacing(10)
        self._label = QLabel(); self._label.setObjectName('field_label')
        root.addWidget(self._label)
        self._spin = QSpinBox(); self._spin.setMinimumHeight(36)
        root.addWidget(self._spin)
        send = QPushButton('Send'); send.setObjectName('btn_send')
        send.clicked.connect(self._send); root.addWidget(send)
        root.addStretch()

    def load(self, label, mn, mx, on_done):
        self._label.setText(label); self._spin.setMinimum(mn)
        self._spin.setMaximum(mx); self._spin.setValue(mn); self._on_done = on_done

    def _send(self):
        self.runner.write(str(self._spin.value()) + ENTER); self.handler.clear()
        if self._on_done: self._on_done()


# ── List Prompt Widget ────────────────────────────────────────────────────────

class ListPromptWidget(QWidget):
    def __init__(self, runner, handler, parent=None):
        super().__init__(parent)
        self.runner   = runner
        self.handler  = handler
        self._on_done = None
        self._cursor  = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14); root.setSpacing(8)

        self._instruction = QLabel('')
        self._instruction.setObjectName('field_label')
        self._instruction.setWordWrap(True)
        self._instruction.hide()
        root.addWidget(self._instruction)

        self._warn = QLabel('Choices not parsed yet.\nUse the number fallback below.')
        self._warn.setObjectName('field_label')
        self._warn.setWordWrap(True); self._warn.hide()
        root.addWidget(self._warn)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._bc = QWidget(); self._bl = QVBoxLayout(self._bc)
        self._bl.setContentsMargins(0, 0, 0, 0)
        self._bl.setSpacing(5); self._bl.addStretch()
        scroll.setWidget(self._bc); root.addWidget(scroll, stretch=1)

        fl = QLabel('Fallback — option number:')
        fl.setObjectName('field_label'); root.addWidget(fl)
        fb_row = QHBoxLayout()
        self._fallback = QLineEdit(); self._fallback.setObjectName('list_fallback')
        self._fallback.setPlaceholderText('0, 1, 2 ...')
        self._fallback.returnPressed.connect(self._send_fallback)
        fb_row.addWidget(self._fallback)
        go = QPushButton('Go'); go.setObjectName('btn_dismiss')
        go.setFixedWidth(50); go.clicked.connect(self._send_fallback)
        fb_row.addWidget(go)
        root.addLayout(fb_row)

    @staticmethod
    def _is_separator(label):
        return len(label.strip().replace('-', '').replace(' ', '')) == 0

    def load(self, title, choices, cursor, on_done, instruction=''):
        self._cursor  = cursor
        self._on_done = on_done
        # Show instruction if provided
        if instruction:
            self._instruction.setText(instruction)
            self._instruction.show()
        else:
            self._instruction.hide()
        while self._bl.count() > 1:
            item = self._bl.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        visible = [c for c in choices if not self._is_separator(c)]
        if visible:
            self._warn.hide()
            for idx, label in enumerate(choices):
                if self._is_separator(label): continue
                display = (label[:42] + '…') if len(label) > 42 else label
                btn = QPushButton(f'  {display}')
                btn.setObjectName('choice_btn')
                btn.setToolTip(label)
                btn.clicked.connect(lambda _, i=idx: self._select(i))
                self._bl.insertWidget(self._bl.count() - 1, btn)
        else:
            self._warn.show()
        self._fallback.clear()

    def _select(self, index):
        navigate_to(self.runner, index, self._cursor)
        self.handler.clear()
        if self._on_done: self._on_done()

    def _send_fallback(self):
        t = self._fallback.text().strip()
        if t.isdigit():
            navigate_to(self.runner, int(t), self._cursor)
            self.handler.clear()
            if self._on_done: self._on_done()


# ── Checkbox Widget ───────────────────────────────────────────────────────────

class CheckboxPromptWidget(QWidget):
    def __init__(self, runner, handler, parent=None):
        super().__init__(parent)
        self.runner = runner; self.handler = handler
        self._choices = []; self._boxes = []; self._on_done = None
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14); root.setSpacing(8)
        br = QHBoxLayout()
        sa = QPushButton('Select all'); sa.setObjectName('btn_select_all')
        sa.clicked.connect(self._select_all); br.addWidget(sa)
        da = QPushButton('Deselect all'); da.setObjectName('btn_deselect_all')
        da.clicked.connect(self._deselect_all); br.addWidget(da)
        root.addLayout(br)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._bc = QWidget(); self._bl = QVBoxLayout(self._bc)
        self._bl.setContentsMargins(4, 4, 4, 4)
        self._bl.setSpacing(2); self._bl.addStretch()
        scroll.setWidget(self._bc); root.addWidget(scroll, stretch=1)
        self._counter = QLabel('0 selected')
        self._counter.setObjectName('field_label')
        self._counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._counter)
        self._confirm_btn = QPushButton('Confirm selection')
        self._confirm_btn.setObjectName('btn_confirm')
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._send)
        root.addWidget(self._confirm_btn)

    def load(self, choices, on_done):
        self._choices = choices; self._on_done = on_done
        while self._bl.count() > 1:
            item = self._bl.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._boxes = []
        for label in choices:
            cb = QCheckBox(label)
            cb.stateChanged.connect(self._update_counter)
            self._bl.insertWidget(self._bl.count() - 1, cb)
            self._boxes.append(cb)
        self._update_counter()

    def _select_all(self):
        for cb in self._boxes: cb.setChecked(True)
    def _deselect_all(self):
        for cb in self._boxes: cb.setChecked(False)
    def _update_counter(self):
        n = sum(1 for cb in self._boxes if cb.isChecked())
        self._counter.setText(f'{n} of {len(self._boxes)} selected')
        self._confirm_btn.setEnabled(n > 0)
    def _send(self):
        selected = [cb.text() for cb in self._boxes if cb.isChecked()]
        select_checkboxes(self.runner, self._choices, selected)
        self.handler.clear()
        if self._on_done: self._on_done()


# ── Side Panel ────────────────────────────────────────────────────────────────

class SidePanel(QWidget):
    def __init__(self, runner, handler, on_reset=None, parent=None):
        super().__init__(parent)
        self.runner    = runner
        self.handler   = handler
        self._on_reset = on_reset
        self.setObjectName('side_panel')
        self.setMinimumWidth(340)
        self.setMaximumWidth(500)
        self._input_esc = False
        self._pending_model_title = 'Select Models'
        self._model_timer = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        hdr = QWidget(); hdr.setObjectName('panel_header')
        hl = QVBoxLayout(hdr); hl.setContentsMargins(12, 10, 12, 10); hl.setSpacing(2)
        self._title    = QLabel('Prompt Panel'); self._title.setObjectName('panel_title')
        self._subtitle = QLabel('Waiting for ofscraper...')
        self._subtitle.setObjectName('panel_subtitle')
        hl.addWidget(self._title); hl.addWidget(self._subtitle)
        root.addWidget(hdr)

        self._stack = QStackedWidget(); root.addWidget(self._stack, stretch=1)

        # 0 — idle
        idle_w = QWidget()
        idle_lay = QVBoxLayout(idle_w)
        idle_lay.setContentsMargins(16, 16, 16, 16); idle_lay.setSpacing(12)
        idle_lbl = QLabel('No prompt detected.\nOutput will appear\nin the terminal.')
        idle_lbl.setObjectName('panel_idle')
        idle_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idle_lay.addWidget(idle_lbl)
        rescan = QPushButton('Rescan for prompt')
        rescan.setObjectName('btn_dismiss')
        rescan.clicked.connect(self._rescan)
        idle_lay.addWidget(rescan); idle_lay.addStretch()
        self._stack.addWidget(idle_w)                           # 0

        self._stack.addWidget(self._make_enter_page())          # 1
        self._stack.addWidget(self._make_confirm_page())        # 2

        self._input_label = QLabel(); self._input_label.setObjectName('field_label')
        self._input_field = QLineEdit(); self._input_field.setObjectName('prompt_input')
        self._input_field.returnPressed.connect(self._send_input)
        self._stack.addWidget(self._make_input_page())          # 3

        self._textarea_label = QLabel(); self._textarea_label.setObjectName('field_label')
        self._textarea_field = QTextEdit(); self._textarea_field.setObjectName('prompt_textarea')
        self._stack.addWidget(self._make_textarea_page())       # 4

        self._list_widget = ListPromptWidget(self.runner, self.handler)
        self._stack.addWidget(self._list_widget)                # 5

        self._checkbox_widget = CheckboxPromptWidget(self.runner, self.handler)
        self._stack.addWidget(self._checkbox_widget)            # 6

        self._model_widget = ModelSelectWidget(self.runner, self.handler)
        self._stack.addWidget(self._model_widget)               # 7

        self._filepath_widget = FilepathWidget(self.runner, self.handler)
        self._stack.addWidget(self._filepath_widget)            # 8

        self._spinbox_widget = SpinboxWidget(self.runner, self.handler)
        self._stack.addWidget(self._spinbox_widget)             # 9

        self._download_widget = DownloadProgressWidget()
        self._stack.addWidget(self._download_widget)            # 10

    def _make_enter_page(self):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(10)
        lbl = QLabel('[?]  Press Enter to continue')
        lbl.setObjectName('prompt_label'); lbl.setWordWrap(True); lay.addWidget(lbl)
        btn = QPushButton('Dismiss  (Enter)'); btn.setObjectName('btn_dismiss')
        btn.clicked.connect(lambda: self._respond(ENTER)); lay.addWidget(btn)
        lay.addStretch(); return w

    def _make_confirm_page(self):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(10)
        self._confirm_label = QLabel()
        self._confirm_label.setObjectName('prompt_label')
        self._confirm_label.setWordWrap(True); lay.addWidget(self._confirm_label)
        yes = QPushButton('Yes'); yes.setObjectName('btn_yes')
        yes.clicked.connect(lambda: self._respond('y\r')); lay.addWidget(yes)
        no = QPushButton('No'); no.setObjectName('btn_no')
        no.clicked.connect(lambda: self._respond('n\r')); lay.addWidget(no)
        lay.addStretch(); return w

    def _make_input_page(self):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(8)
        lay.addWidget(self._input_label)
        lay.addWidget(self._input_field)
        send = QPushButton('Send'); send.setObjectName('btn_send')
        send.clicked.connect(self._send_input); lay.addWidget(send)
        hint = QLabel('or press Enter in the field')
        hint.setObjectName('field_label')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.addWidget(hint)
        lay.addStretch(); return w

    def _make_textarea_page(self):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(8)
        lay.addWidget(self._textarea_label)
        self._textarea_field.setMinimumHeight(120); lay.addWidget(self._textarea_field)
        send = QPushButton('Send'); send.setObjectName('btn_send')
        send.clicked.connect(self._send_textarea); lay.addWidget(send)
        lay.addStretch(); return w

    def _rescan(self):
        self.handler._scan()

    @pyqtSlot(str, dict)
    def show_prompt(self, ptype, kwargs):
        self._subtitle.setText(f'Detected: {ptype}')
        if ptype == 'enter':
            self._title.setText('[?]  Press Enter')
            self._stack.setCurrentIndex(1)
        elif ptype == 'confirm':
            self._title.setText('[?]  Confirm')
            self._confirm_label.setText(kwargs.get('question', 'Continue?'))
            self._stack.setCurrentIndex(2)
        elif ptype == 'input':
            label = kwargs.get('label', 'Input')
            self._input_esc = kwargs.get('esc', False)
            self._title.setText(f'[?]  {label}')
            self._input_label.setText(label)
            self._input_field.clear(); self._input_field.setFocus()
            self._stack.setCurrentIndex(3)
        elif ptype == 'textarea':
            label = kwargs.get('label', 'Input')
            self._title.setText(f'[?]  {label}')
            self._textarea_label.setText(label)
            self._textarea_field.clear(); self._textarea_field.setFocus()
            self._stack.setCurrentIndex(4)
        elif ptype == 'list':
            title   = kwargs.get('title', 'Select')
            choices = kwargs.get('choices', [])
            cursor  = kwargs.get('cursor', 0)
            instruction = kwargs.get('instruction', '')
            self._title.setText(f'[?]  {title}')
            self._subtitle.setText(f'{len(choices)} options' if choices else 'parsing...')
            self._list_widget.load(title, choices, cursor, self.reset, instruction=instruction)
            self._stack.setCurrentIndex(5)
        elif ptype == 'checkbox':
            title   = kwargs.get('title', 'Select areas')
            choices = kwargs.get('choices', [])
            self._title.setText(f'[?]  {title}')
            self._subtitle.setText(f'{len(choices)} areas')
            self._checkbox_widget.load(choices, self.reset)
            self._stack.setCurrentIndex(6)
        elif ptype == 'model':
            title = kwargs.get('title', 'Select Models')
            self._pending_model_title = title
            self._title.setText(f'[?]  {title}')
            self._subtitle.setText('Loading model list...')
            self._stack.setCurrentIndex(7)
        elif ptype == 'filepath':
            label   = kwargs.get('label', 'Path')
            dir_only = kwargs.get('dir_only', False)
            self._title.setText(f'[?]  {label}')
            self._subtitle.setText('folder' if dir_only else 'file')
            self._filepath_widget.load(label, dir_only, self.reset)
            self._stack.setCurrentIndex(8)
        elif ptype == 'spinbox':
            label = kwargs.get('label', 'Value')
            self._title.setText(f'[?]  {label}')
            self._subtitle.setText(f'{kwargs.get("min", 0)} – {kwargs.get("max", 100)}')
            self._spinbox_widget.load(
                label, kwargs.get('min', 0), kwargs.get('max', 100), self.reset)
            self._stack.setCurrentIndex(9)

    def _populate_models(self):
        models = self.handler._model_cache
        self._subtitle.setText(f'{len(models)} models')
        self._model_widget.load(models, self.reset)

    # ── Download progress (called from MainWindow._on_output) ─────────────

    def show_download(self, username):
        self._title.setText('Downloading')
        self._subtitle.setText(username)
        self._download_widget.set_user(username)
        self._stack.setCurrentIndex(10)

    def set_download_path(self, path):
        self._download_widget.set_path(path)

    def update_download_stats(self, photos, videos, audios, skipped, failed):
        self._download_widget.update_stats(photos, videos, audios, skipped, failed)

    def reset(self):
        self._title.setText('Prompt Panel')
        self._subtitle.setText('Waiting for ofscraper...')
        self._stack.setCurrentIndex(0)
        if self._on_reset:
            self._on_reset()

    def _respond(self, text):
        self.runner.write(text); self.handler.clear(); self.reset()

    def _send_input(self):
        suffix = '\x1b\r' if self._input_esc else ENTER
        self._respond(self._input_field.text() + suffix)

    def _send_textarea(self):
        self._respond(self._textarea_field.toPlainText() + '\x1b')


# ── Launcher Bar ──────────────────────────────────────────────────────────────

class LauncherBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName('launcher_bar'); self._build()

    def _build(self):
        lay = QHBoxLayout(self); lay.setContentsMargins(10, 6, 10, 6); lay.setSpacing(8)
        lbl = QLabel('ofscraper')
        lbl.setStyleSheet('color:#69f0ae;font-family:Courier New;font-size:10pt;font-weight:bold;')
        lay.addWidget(lbl)
        al = QLabel('args:'); al.setStyleSheet('color:#8b949e;font-size:9pt;'); lay.addWidget(al)
        self.args_input = QLineEdit(); self.args_input.setObjectName('args_input')
        self.args_input.setPlaceholderText(
            'blank = main menu  —  or:  -u username  /  -0 username timeline -1')
        self.args_input.returnPressed.connect(self._on_launch); lay.addWidget(self.args_input, stretch=1)
        self.launch_btn = QPushButton('Launch'); self.launch_btn.setObjectName('btn_launch')
        self.launch_btn.clicked.connect(self._on_launch); lay.addWidget(self.launch_btn)
        self.restart_btn = QPushButton('Restart'); self.restart_btn.setObjectName('btn_restart')
        self.restart_btn.setEnabled(False); self.restart_btn.setToolTip('Ctrl+R')
        lay.addWidget(self.restart_btn)
        self.stop_btn = QPushButton('Stop'); self.stop_btn.setObjectName('btn_stop')
        self.stop_btn.setEnabled(False); lay.addWidget(self.stop_btn)

    def _on_launch(self):
        self.launch_btn.setEnabled(False)
        self.restart_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.args_input.setEnabled(False)

    def on_stopped(self):
        self.launch_btn.setEnabled(True)
        self.restart_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.args_input.setEnabled(True)

    def build_command(self):
        base = ['ofscraper']
        raw  = self.args_input.text().strip()
        if raw:
            base += shlex.split(raw)
        return base


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._settings = QSettings('ofscraper', 'gui')
        self.runner = None
        self.side_panel = None
        self.setWindowTitle('OF-Scraper GUI')
        if getattr(sys, 'frozen', False):
            self.setWindowIcon(QIcon(os.path.join(sys._MEIPASS, 'OF-GUI.ico')))
        else:
            self.setWindowIcon(QIcon('OF-GUI.ico'))
        self.setStyleSheet(DARK_STYLE)
        self._build_ui()
        self._restore_geometry()

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self.launcher = LauncherBar()
        self.launcher.launch_btn.clicked.connect(self._start_scraper)
        self.launcher.restart_btn.clicked.connect(self._restart_scraper)
        root.addWidget(self.launcher)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)
        self.terminal = TerminalDisplay()
        self.splitter.addWidget(self.terminal)

        # Placeholder right panel before first launch
        ph = QWidget(); ph.setObjectName('side_panel'); ph.setMinimumWidth(280)
        pl = QLabel('Launch ofscraper\nto begin.'); pl.setObjectName('panel_idle')
        pl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        QVBoxLayout(ph).addWidget(pl)
        self.splitter.addWidget(ph)
        self.splitter.setStretchFactor(0, 3); self.splitter.setStretchFactor(1, 1)
        root.addWidget(self.splitter, stretch=1)

        ib = QWidget(); ib.setObjectName('input_bar')
        bar = QHBoxLayout(ib); bar.setContentsMargins(8, 5, 8, 5); bar.setSpacing(6)
        arrow = QLabel('›'); arrow.setStyleSheet('color:#2ea043;font-size:13pt;padding:0 4px;')
        bar.addWidget(arrow)
        self.raw_input = QLineEdit(); self.raw_input.setObjectName('raw_input')
        self.raw_input.setPlaceholderText('Raw input fallback')
        self.raw_input.returnPressed.connect(self._send_raw)
        bar.addWidget(self.raw_input, stretch=1)
        sb = QPushButton('Send'); sb.setFixedWidth(64); sb.clicked.connect(self._send_raw)
        bar.addWidget(sb)
        ctrlc = QPushButton('⌃C'); ctrlc.setObjectName('btn_stop')
        ctrlc.setFixedWidth(48); ctrlc.setToolTip('Send Ctrl+C')
        ctrlc.clicked.connect(self._send_ctrl_c); bar.addWidget(ctrlc)
        root.addWidget(ib)

        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.status.showMessage('Ready — click Launch to start ofscraper')

        QShortcut(QKeySequence('Ctrl+W'), self).activated.connect(self.close)
        QShortcut(QKeySequence('Ctrl+R'), self).activated.connect(self._restart_scraper)

    def _start_scraper(self):
        self._mdl_scrolled = False
        if self.runner:
            try:
                self.runner.process_ended.disconnect()
                self.runner.output_received.disconnect()
            except Exception:
                pass
            self.runner.stop()

        self.runner = ProcessRunner()
        self.handler = PromptHandler()

        self.runner.output_received.connect(self.terminal.append_ansi)
        self.runner.output_received.connect(self.handler.feed)
        self.runner.output_received.connect(self._on_output)
        self.runner.process_ended.connect(self._on_exit)

        self.side_panel = SidePanel(self.runner, self.handler,
                                    on_reset=self._on_prompt_done)
        self.handler.prompt_detected.connect(self.side_panel.show_prompt)
        self.handler.prompt_detected.connect(self._on_prompt_detected)
        self.splitter.replaceWidget(1, self.side_panel)
        self.splitter.setStretchFactor(0, 3); self.splitter.setStretchFactor(1, 1)

        self.launcher.stop_btn.clicked.connect(self._stop_scraper)

        command = self.launcher.build_command()
        self.runner.start(command)
        self.setWindowTitle(f'OF-Scraper GUI  [{" ".join(command)}]')
        self.status.showMessage(f'Starting: {" ".join(command)}')


    def _restart_scraper(self):
        self.terminal.clear()
        self._start_scraper()
        self.launcher._on_launch()

    def _stop_scraper(self):
        if self.runner: self.runner.stop()

    @pyqtSlot(str, dict)
    def _on_prompt_detected(self, ptype, kwargs):
        if ptype == 'model':
            import json, os, tempfile
            try:
                _tmp = os.path.join(tempfile.gettempdir(), 'ofscraper_models.json')
                if os.path.exists(_tmp):
                    with open(_tmp) as f:
                        models = json.load(f)
                    self.side_panel._model_widget.load(models, self.side_panel.reset)
                    self.side_panel._subtitle.setText(f'{len(models)} models')
            except Exception:
                pass
        self.terminal._auto_scroll = False


    def _on_prompt_done(self):
        self.terminal._auto_scroll = True
        self.terminal._scroll_to_bottom()

    def _on_output(self, raw):
        if not (self.runner and self.runner.pid):
            return
        self.status.showMessage(f'Running  ·  PID {self.runner.pid}  ·  PTY connected')
        if not self.side_panel:
            return

        clean = _ANSI_STRIP.sub('', raw)

        # Show processing state during subscription fetch
        if 'Getting subscriptions' in clean:
            self.side_panel._title.setText('Please wait')
            self.side_panel._subtitle.setText('Fetching subscriptions...')
            self.side_panel._stack.setCurrentIndex(0)

        # Show processing state during content fetch
        if 'Getting [' in clean:
            self.side_panel._title.setText('Please wait')
            self.side_panel._subtitle.setText('Fetching content...')
            self.side_panel._stack.setCurrentIndex(0)

        # Download: detect active model
        m = _DL_USER_RE.search(clean)
        if m:
            self.side_panel.show_download(m.group(1))

        # Download: save path
        m = _DL_PATH_RE.search(clean)
        if m:
            self.side_panel.set_download_path(m.group(1).strip())

        # Download: progress stats
        m = _DL_PROG_RE.search(clean)
        if m:
            self.side_panel.update_download_stats(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)))

        # Processing indicator when panel is idle
        if self.side_panel._stack.currentIndex() == 0:
            if 'Getting subscriptions' not in clean and 'Getting [' not in clean:
                self.side_panel._subtitle.setText('Processing...')
            if not hasattr(self, '_idle_timer'):
                self._idle_timer = QTimer()
                self._idle_timer.setSingleShot(True)
                self._idle_timer.timeout.connect(self._on_idle)
            self._idle_timer.start(2000)

    def _on_idle(self):
        if self.side_panel and self.side_panel._stack.currentIndex() == 0:
            self.side_panel._title.setText('Prompt Panel')
            self.side_panel._subtitle.setText('Waiting for ofscraper...')

    def _on_exit(self, code):
        self.status.showMessage(f'Process exited  ·  exit code {code}')
        self.setWindowTitle('OF-Scraper GUI  [stopped]')
        self.launcher.on_stopped()
        if self.side_panel:
            self.side_panel.reset()


    def _send_raw(self):
        text = self.raw_input.text()
        if text and self.runner:
            self.runner.write(text + ENTER); self.raw_input.clear()

    def _send_ctrl_c(self):
        if self.runner: self.runner.write('\x03')

    def _restore_geometry(self):
        geom = self._settings.value('geometry')
        if geom: self.restoreGeometry(geom)
        else: self.resize(1280, 760)
        state = self._settings.value('splitter')
        if state: self.splitter.restoreState(state)

    def closeEvent(self, event):
        self._settings.setValue('geometry', self.saveGeometry())
        self._settings.setValue('splitter', self.splitter.saveState())
        if self.runner: self.runner.stop()
        event.accept()


def run():
    app = QApplication(sys.argv)
    app.setFont(QFont('Arial', 10))
    
    # ── Taskbar icon ──────────────────────────────────────
    import os
    from PyQt6.QtGui import QIcon
    ico = os.path.join(os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, 'frozen', False) else __file__
    )), 'OF-GUI.ico')
    if os.path.exists(ico):
        app.setWindowIcon(QIcon(ico))
    # ─────────────────────────────────────────────────────
    
    w = MainWindow(); w.show()
    sys.exit(app.exec())
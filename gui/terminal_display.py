import re
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat

# Colors, SGR codes (unchanged)
ANSI_RE = re.compile(
    r'\x1b\[[0-9;]*[mBCDEFGHJKLMPSTfnsu]'   # everything EXCEPT cursor-up (A)
    r'|\x1b\[\?[0-9;]+[hl]'
    r'|\x1b[=>]'
)
CURSOR_UP_RE = re.compile(r'\x1b\[(\d*)A')   # cursor-up: \x1b[NA or \x1b[A

SGR_COLORS = {
    '0': '#c9d1d9', '1': '#e6edf3',
    '30': '#484f58', '31': '#ef9a9a', '32': '#69f0ae', '33': '#ffd54f',
    '34': '#79c0ff', '35': '#c792ea', '36': '#64b5f6', '37': '#c9d1d9',
    '90': '#8b949e', '91': '#f97583', '92': '#69f0ae', '93': '#ffd54f',
    '94': '#79c0ff', '95': '#c792ea', '96': '#64b5f6', '97': '#e6edf3',
}


def _parse_sgr(esc):
    if not esc.endswith('m'):
        return None
    for p in reversed(esc[2:-1].split(';')):
        if p in SGR_COLORS:
            return SGR_COLORS[p]
    return None


class TerminalDisplay(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont('Courier New', 10))
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #c9d1d9;
                border: none;
                padding: 8px;
                selection-background-color: #264f78;
            }
            QScrollBar:vertical {
                background: #0d1117; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #30363d; border-radius: 4px; min-height: 24px;
            }
            QScrollBar::handle:vertical:hover { background: #484f58; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal { height: 0px; }
        """)
        self._color         = '#c9d1d9'
        self._auto_scroll   = True
        self._programmatic  = False
        self._overwrite_lines = 0   # pending cursor-up from previous Rich render
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def _on_scroll(self, value):
        if self._programmatic:
            return
        sb = self.verticalScrollBar()
        self._auto_scroll = (value >= sb.maximum() - 4)

    def _scroll_to_bottom(self):
        self._programmatic = True
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        self._programmatic = False

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self._auto_scroll = False
        super().wheelEvent(event)
        sb = self.verticalScrollBar()
        if sb.value() >= sb.maximum() - 4:
            self._auto_scroll = True

    def append_ansi(self, raw):
        at_bottom = self._auto_scroll
        cursor = self.textCursor()

        # ── Always strip cursor-up codes so they never appear as text ────
        # Store the count for live-display overwrite, but strip from ALL output
        pending = 0
        def _extract_up(m):
            nonlocal pending
            n = int(m.group(1)) if m.group(1) else 1
            pending += n
            return ''
        raw = CURSOR_UP_RE.sub(_extract_up, raw)

        # Check if this is a Rich live display panel (Activity Progress)
        is_live_content = 'Activity Progress' in raw or 'Getting subscriptions' in raw

        # ── In-place overwrite for live panels ──────────────────────────
        if is_live_content and self._overwrite_lines > 0:
            n = self._overwrite_lines
            self._overwrite_lines = 0
            cursor.movePosition(QTextCursor.MoveOperation.End)
            for _ in range(n):
                cursor.movePosition(QTextCursor.MoveOperation.Up)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            cursor.movePosition(QTextCursor.MoveOperation.End,
                                QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            if not cursor.atStart():
                cursor.movePosition(QTextCursor.MoveOperation.Left,
                                    QTextCursor.MoveMode.KeepAnchor)
                if cursor.selectedText() == '\n':
                    cursor.removeSelectedText()
            self.setTextCursor(cursor)
        elif not is_live_content:
            # Not live content — discard any pending overwrite
            self._overwrite_lines = 0
            cursor.movePosition(QTextCursor.MoveOperation.End)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.End)

        # Store pending for next call (live content only)
        if is_live_content and pending > 0:
            self._overwrite_lines = pending

        # Process remaining ANSI codes and text
        parts = ANSI_RE.split(raw)
        codes = ANSI_RE.findall(raw)
        for i, chunk in enumerate(parts):
            if chunk:
                self._insert_chunk(cursor, chunk)
            if i < len(codes):
                c = _parse_sgr(codes[i])
                if c:
                    self._color = c

        self.setTextCursor(cursor)
        if at_bottom:
            self._scroll_to_bottom()

    def _insert_chunk(self, cursor, chunk):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self._color))
        i = 0
        while i < len(chunk):
            ch = chunk[i]
            if ch == '\r':
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            elif ch == '\n':
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertText('\n', fmt)
            else:
                j = i
                while j < len(chunk) and chunk[j] not in ('\r', '\n'):
                    j += 1
                run = chunk[i:j]
                if run:
                    sel = QTextCursor(cursor)
                    sel.movePosition(QTextCursor.MoveOperation.Right,
                                     QTextCursor.MoveMode.KeepAnchor, len(run))
                    if not sel.atBlockEnd():
                        cursor.setPosition(sel.anchor())
                        cursor.setPosition(sel.position(),
                                           QTextCursor.MoveMode.KeepAnchor)
                    cursor.insertText(run, fmt)
                i = j
                continue
            i += 1
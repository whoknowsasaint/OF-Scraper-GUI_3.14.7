import re
import time
from PyQt6.QtCore import QObject, pyqtSignal


ANSI_RE = re.compile(
    r'\x1b\[[0-9;]*[mABCDEFGHJKLMPSTfnsu]'
    r'|\x1b\[\?[0-9;]+[hl]'
    r'|\x1b[=>]'
)


def _strip(text):
    return ANSI_RE.sub('', text)


def parse_list_choices(buf):
    """Returns (choices, cursor_index). cursor = index of ❯-focused item."""
    clean = _strip(buf)
    lines = clean.splitlines()
    start = 0
    for i, line in enumerate(lines):
        if re.search(r'\[\?\]|^\s*\?', line):
            start = i

    arrow_re  = re.compile(r'^[ \t]*[❯>][ \t]+(.+)$')
    indent_re = re.compile(r'^[ \t]{2,}(.+)$')
    log_re    = re.compile(r'^\[[\w.]+:\d+\]')
    url_re    = re.compile(r'^https?://')

    choices = []
    cursor_pos = 0
    nav_idx    = 0

    for line in lines[start:]:
        label      = None
        has_cursor = False
        m = arrow_re.match(line)
        if m:
            label = m.group(1).strip(); has_cursor = True
        else:
            m = indent_re.match(line)
            if m:
                label = m.group(1).strip()

        if not label: continue
        if '[?]' in label or label.startswith('?'): continue
        if log_re.match(label) or url_re.match(label): continue
        if label.startswith('['): continue
        if label.strip().replace('-', '').replace(' ', '') == '': continue

        if has_cursor:
            cursor_pos = nav_idx
        choices.append(label)
        nav_idx += 1

    return choices, cursor_pos


def parse_checkbox_choices(buf):
    clean = _strip(buf)
    lines = clean.splitlines()
    start = 0
    for i, line in enumerate(lines):
        if re.search(r'\[\?\]|^\s*\?', line):
            start = i
    re_    = re.compile(r'^[ \t]*[❯>]?[ \t]*[◉◯○●□■✓✗oO\-][ \t]+(.+)$')
    log_re = re.compile(r'^\[[\w.]+:\d+\]')
    choices = []
    for line in lines[start:]:
        m = re_.match(line)
        if not m: continue
        label = m.group(1).strip()
        if not label or '[?]' in label or log_re.match(label): continue
        choices.append(label)
    return choices


def _parse_model_list(buf):
    clean = _strip(buf)
    re_   = re.compile(r'\b(\d+):\s+([\w][\w\-\.]*)\s*=>')
    models, seen = [], set()
    for m in re_.finditer(clean):
        u = m.group(2).strip()
        if u and u not in seen:
            seen.add(u); models.append(u)
    return models


# ── Patterns ──────────────────────────────────────────────────────────────────

DOWNLOAD_AREAS = ['Profile', 'Timeline', 'Pinned', 'Archived', 'Highlights',
                  'Stories', 'Messages', 'Purchased', 'Streams']
LIKE_AREAS     = ['Timeline', 'Pinned', 'Archived', 'Streams']

CONFIG_FILEPATH_PROMPTS = [
    (r'save_location',          'save location',        True),
    (r'ffmpeg path',            'ffmpeg executable',    False),
    (r'path to client id file', 'client id file',       False),
    (r'path to private.?key',   'private key file',     False),
    (r'root database folder',   'root database folder', True),
    (r'Merge db folder',        'merge db folder',      True),
]
CONFIG_SPINBOX_PROMPTS = [
    (r'min length',                      'min length',            0, 99999),
    (r'max length',                      'max length',            0, 99999),
    (r'Number of semaphores per thread', 'semaphores per thread', 1, 15),
]
CONFIG_INPUT_PROMPTS = [
    (r'minimum free space',             'minimum free space'),
    (r'space-replacer',                 'space replacer'),
    (r'Maximum download speed',         'max download speed'),
    (r'discord webhook',                'discord webhook URL'),
    (r'dir_format',                     'dir_format'),
    (r'file_format',                    'file_format'),
    (r'Script to run after each model', 'post-model script'),
    (r'textlength',                     'text length'),
]
FILTER_LIST_PROMPTS = [
    (r'Make changes to model list Filters',        'Model Filters'),
    (r'Sort Accounts by',                           'Sort By'),
    (r'Sort Direction',                             'Sort Direction'),
    (r'Filter account by whether renewal',          'Renewal Filter'),
    (r'Filter accounts based on access',            'Access Filter'),
    (r'Filter Accounts By visability of last seen', 'Last Seen Filter'),
    (r'Filter Accounts By whether free trial',      'Free Trial Filter'),
    (r'Which price do you want to modify',          'Price Filter'),
    (r'Filter accounts by.*price',                  'Price Type'),
    (r'Do you want to reset username info',         'Reset Username?'),
    (r'Select default key mode',                    'Key Mode'),
    (r'text type',                                  'Text Type'),
    (r'Should the script truncate',                 'Truncate?'),
    (r'Enable auto file resume',                    'Auto Resume?'),
    (r'Verify the integrity of ALL videos',         'Verify Videos?'),
]
FILTER_DATE_PROMPTS = [
    (r'last seen being after',  'last seen after  (YYYY-MM-DD)'),
    (r'last seen being before', 'last seen before (YYYY-MM-DD)'),
]
FILTER_TEXTAREA_PROMPTS = [
    (r'Change User List',  'User List  (one per line)'),
    (r'Change Black List', 'Black List (one per line)'),
]
CHECKBOX_PROMPTS = [
    (r'Which area.*download',          'Download Areas',    DOWNLOAD_AREAS),
    (r'Which area.*like.{0,10}unlike', 'Like/Unlike Areas', LIKE_AREAS),
    (r'Which area.*perform like',      'Like/Unlike Areas', LIKE_AREAS),
    (r'Which area.*perform download',  'Download Areas',    DOWNLOAD_AREAS),
    (r'Which area.*metadata',          'Metadata Areas',    DOWNLOAD_AREAS),
    (r'Which area.*database',          'Database Areas',    DOWNLOAD_AREAS),
]
MODEL_PROMPTS = [
    (r'Which models do you want to scrape', 'Select Models'),
    (r'Select models',                       'Select Models'),
    (r'Filter:.*\d+/\d+',                   'Select Models'),
]
LIST_PROMPTS = [
    (r'Main Menu.*What would you like to do',      'Main Menu'),
    (r'Config Menu.*Which area',                    'Config Menu'),
    (r'Profile Menu.*Select one',                   'Profile Menu'),
    (r'Auth Menu.*Select how to retrieve',          'Auth Setup'),
    (r'Do you want to reset selected area',         'Reset Area?'),
    (r'Do you want to reset the selected like',     'Reset Likes?'),
    (r'Do you want to reset the selected download', 'Reset Downloads?'),
    (r'Do you want to continue with script',        'Continue?'),
    (r'How do you want to fix this issue',          'Fix Issue'),
    (r'Rescan account for users',                   'Rescan Accounts?'),
    (r'Select Profile',                             'Select Profile'),
    (r'Which profile would you like to edit',       'Edit Profile'),
    (r'Set this as the new default profile',        'Default Profile?'),
    (r'Confirm merge',                              'Confirm Merge'),
    (r'Do another merge',                           'Another Merge?'),
]
# Prompts that echo their answer and need cooldown to prevent re-trigger
COOLDOWN_LIST_PROMPTS = [
    (r'Scrape labels',            'Scrape Labels?',  ['True', 'False'], 1, '[This is mainly for data enhancement]'),
    (r'Scrape entire paid page',  'Paid Page?',      ['True', 'False'], 1, 'Warning: initial Scan can be slow\nCaution: You should not need this unless you are looking to scrape paid content from a deleted/banned model'),
    (r'Would you like to redownload', 'Redownload all?', ['Yes', 'No'], 1, ''),
]
ACTION_MENU_FALLBACK = [
    'Download content from a user',
    "Like a selection of a user's posts",
    "Unlike a selection of a user's posts",
    "Download content from a user + Like a selection of a user's posts",
    "Download content from a user + Unlike a selection of a user's posts",
    'Go to main menu',
    'Quit',
]
SIMPLE_PROMPTS = [
    (r'Press enter to continue',          'enter',    {}),
    (r'Enter.*sess.?cookie',              'input',    {'label': 'sess cookie',         'esc': True}),
    (r'Enter.*auth_id',                   'input',    {'label': 'auth_id cookie',      'esc': True}),
    (r'Enter.*auth_uid',                  'input',    {'label': 'auth_uid (optional)', 'esc': True}),
    (r'Enter.*user.?agent',               'input',    {'label': 'user_agent',          'esc': True}),
    (r'Enter.*x-bc',                      'input',    {'label': 'x-bc token',          'esc': True}),
    (r'Paste Text from Extension',        'textarea', {'label': 'Extension JSON'}),
    (r'Edit auth text',                   'textarea', {'label': 'Auth JSON'}),
    (r'Is the auth information correct',  'confirm',  {}),
    (r'Have you backed up',               'confirm',  {}),
    (r'Would you like to make one',       'confirm',  {}),
    (r'Do you want to continue',          'confirm',  {}),
    (r'[Ww]hat would you like to rename', 'input',    {'label': 'new name'}),
    (r'[Ww]hat would you like to name',   'input',    {'label': 'name'}),
]


class PromptHandler(QObject):
    prompt_detected = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buf              = ''
        self._model_cache      = []
        self._model_cache_seen = set()
        self._last_emit_key    = None
        self._last_emit_time   = 0.0

    def feed(self, raw):
        clean      = _strip(raw)
        self._buf += clean
        self._buf  = self._buf[-8000:]
        self._accumulate_models(clean)
        self._scan()

    def clear(self):
        self._buf = ''

    def _accumulate_models(self, clean):
        re_ = re.compile(r'\b(\d+):\s+([\w][\w\-\.]*)\s*=>')
        for m in re_.finditer(clean):
            u = m.group(2).strip()
            if u and u not in self._model_cache_seen:
                self._model_cache_seen.add(u)
                self._model_cache.append(u)

    def _emit(self, ptype, kwargs, cooldown=0.0):
        key = (ptype, kwargs.get('title', ''))
        now = time.time()
        if cooldown > 0 and key == self._last_emit_key:
            if now - self._last_emit_time < cooldown:
                self._buf = ''
                return
        self._last_emit_key  = key
        self._last_emit_time = now
        self._buf = ''
        self.prompt_detected.emit(ptype, kwargs)

    def _scan(self):
        for p, label, d in CONFIG_FILEPATH_PROMPTS:
            if re.search(p, self._buf, re.IGNORECASE):
                self._emit('filepath', {'label': label, 'dir_only': d}); return
        for p, label, mn, mx in CONFIG_SPINBOX_PROMPTS:
            if re.search(p, self._buf, re.IGNORECASE):
                self._emit('spinbox', {'label': label, 'min': mn, 'max': mx}); return
        for p, title in FILTER_LIST_PROMPTS:
            if re.search(p, self._buf, re.IGNORECASE):
                c, cur = parse_list_choices(self._buf)
                self._emit('list', {'title': title, 'choices': c, 'cursor': cur}); return
        for p, label in FILTER_DATE_PROMPTS:
            if re.search(p, self._buf, re.IGNORECASE):
                self._emit('input', {'label': label}); return
        for p, label in FILTER_TEXTAREA_PROMPTS:
            if re.search(p, self._buf, re.IGNORECASE):
                self._emit('textarea', {'label': label}); return
        for p, label in CONFIG_INPUT_PROMPTS:
            if re.search(p, self._buf, re.IGNORECASE):
                self._emit('input', {'label': label}); return
        for p, title, fallback in CHECKBOX_PROMPTS:
            if re.search(p, self._buf, re.IGNORECASE):
                choices = parse_checkbox_choices(self._buf) or fallback
                self._emit('checkbox', {'title': title, 'choices': choices}); return
        for p, title in MODEL_PROMPTS:
            if re.search(p, self._buf, re.IGNORECASE):
                self._emit('model', {'title': title}, cooldown=3.0); return
        # Action Menu with fallback
        if re.search(r'Action Menu.*What action', self._buf, re.IGNORECASE):
            c, cur = parse_list_choices(self._buf)
            if not c:
                c = ACTION_MENU_FALLBACK; cur = 0
            self._emit('list', {'title': 'Action Menu', 'choices': c, 'cursor': cur}); return
        # Cooldown prompts (echo-safe)
        for p, title, fallback, cur_default, instruction in COOLDOWN_LIST_PROMPTS:
            if re.search(p, self._buf, re.IGNORECASE):
                c, cur = parse_list_choices(self._buf)
                if not c:
                    c = fallback; cur = cur_default
                self._emit('list', {'title': title, 'choices': c, 'cursor': cur, 'instruction': instruction},
                           cooldown=5.0); return
        for p, title in LIST_PROMPTS:
            if re.search(p, self._buf, re.IGNORECASE):
                c, cur = parse_list_choices(self._buf)
                self._emit('list', {'title': title, 'choices': c, 'cursor': cur}); return
        for p, ptype, kwargs in SIMPLE_PROMPTS:
            if re.search(p, self._buf, re.IGNORECASE):
                self._emit(ptype, dict(kwargs)); return
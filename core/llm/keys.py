import importlib.util, json, os
from core.paths import TAUKEY_PATH

_taukey_path = _taukey_mtime = None
taukeys = {}

def _load_taukeys():
    global _taukey_path
    p = str(TAUKEY_PATH)
    if TAUKEY_PATH.exists():
        spec = importlib.util.spec_from_file_location("taukey", p)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        _taukey_path = p
        return {k: v for k, v in vars(mod).items() if not k.startswith('_')}
    legacy = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'taukey.json')
    if os.path.exists(legacy):
        _taukey_path = legacy
        with open(legacy, encoding='utf-8') as f: return json.load(f)
    raise Exception(
        f'[ERROR] {p} not found. Run `tau configure` to generate one from taukey_template.'
    )

def reload_taukeys():
    global _taukey_mtime, taukeys
    mt = os.stat(_taukey_path).st_mtime_ns if _taukey_path else -1
    if mt == _taukey_mtime: return taukeys, False
    mk = _load_taukeys(); _taukey_mtime = os.stat(_taukey_path).st_mtime_ns
    print(f'[Info] Load taukeys from {_taukey_path}')
    taukeys = mk
    return mk, True

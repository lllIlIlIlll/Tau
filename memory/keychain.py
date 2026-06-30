"""Keychain: save key to a file, then keys.set("name", file="path"); keys.name.use() to retrieve (use but no print)."""
import json, os, hashlib, pathlib, getpass

_PATH = pathlib.Path.home() / "tau_keychain.enc"
_OLD_PATH = pathlib.Path.home() / "ga_keychain.enc"
try: _user = os.getlogin()
except OSError: _user = getpass.getuser()
_MASK = hashlib.sha256(f"{_user}@tau_keychain".encode()).digest()
_OLD_MASK = hashlib.sha256(f"{_user}@ga_keychain".encode()).digest()

def _xor(data: bytes, mask: bytes = _MASK) -> bytes:
    return bytes(b ^ mask[i % len(mask)] for i, b in enumerate(data))

class SecretStr:
    def __init__(self, name: str, val: str):
        self._name, self._val = name, val
    def use(self) -> str:
        return self._val
    def __repr__(self):
        n = len(self._val)
        if n <= 4:     preview = '***'
        elif n <= 16:  preview = f"{self._val[:3]}···{self._val[-3:]}"
        elif n <= 40:  preview = f"{self._val[:6]}···{self._val[-6:]} len={n}"
        else:          preview = f"{self._val[:10]}···{self._val[-6:]} len={n}"
        return f"SecretStr({self._name}={preview}) # .use() to get raw, do not print raw value"
    __str__ = __repr__

class _Keys:
    def __init__(self):
        self._d = {}
        if _PATH.exists():
            try:
                self._d = json.loads(_xor(_PATH.read_bytes()))
                return
            except Exception as e:
                print(f"[keychain] WARNING: failed to load {_PATH}: {e}")
                print(f"[keychain] Starting with empty keychain. Old file kept as .bak")
                _PATH.rename(_PATH.with_suffix('.enc.bak'))
        # One-shot migration from legacy ~/ga_keychain.enc (old XOR salt)
        if _OLD_PATH.exists():
            try:
                self._d = json.loads(_xor(_OLD_PATH.read_bytes(), _OLD_MASK))
                _PATH.write_bytes(_xor(json.dumps(self._d).encode()))
                _OLD_PATH.unlink()
                print(f"[keychain] migrated legacy {_OLD_PATH} → {_PATH}")
                return
            except Exception as e:
                print(f"[keychain] legacy migration failed: {e} — old file kept as .bak")
                _OLD_PATH.rename(_OLD_PATH.with_suffix('.enc.bak'))
    def __getattr__(self, k):
        if k.startswith('_'): raise AttributeError(k)
        if k not in self._d: raise KeyError(f"No secret: {k}")
        return SecretStr(k, self._d[k])
    def set(self, k, v=None, *, file=None):
        if file: v = pathlib.Path(file).read_text().strip()
        self._d[k] = v
        _PATH.write_bytes(_xor(json.dumps(self._d).encode()))
    def ls(self): return list(self._d.keys())

keys = _Keys()

def __getattr__(name): return getattr(keys, name)

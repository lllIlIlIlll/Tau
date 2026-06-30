import os, re, time, requests
from datetime import datetime
from ..paths import TEMP
from .trim import safeprint
print = safeprint

def auto_make_url(base, path):
    b, p = base.rstrip('/'), path.strip('/')
    if b.endswith('$'): return b[:-1].rstrip('/')
    if b.endswith(p): return b
    return f"{b}/{p}" if re.search(r'/v\d+(/|$)', b) else f"{b}/v1/{p}"

def _record_usage(usage, api_mode):
    if not usage: return
    if api_mode == 'responses':
        cached = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
        inp = usage.get("input_tokens", 0); out = usage.get("output_tokens", 0)
        print(f"[Cache] input={inp} cached={cached}")
        if out: print(f"[Output] tokens={out}")
    elif api_mode == 'chat_completions':
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        inp = usage.get("prompt_tokens", 0); out = usage.get("completion_tokens", 0)
        print(f"[Cache] input={inp} cached={cached}")
        if out: print(f"[Output] tokens={out}")
    elif api_mode == 'messages':
        ci, cr, inp = usage.get("cache_creation_input_tokens", 0), usage.get("cache_read_input_tokens", 0), usage.get("input_tokens", 0)
        print(f"[Cache] input={inp} creation={ci} read={cr}")

def _stream_with_retry(sess, url, headers, payload, parse_fn):
    _RETRYABLE = {408, 409, 425, 429, 500, 502, 503, 504, 529}
    def _delay(resp, attempt):
        try: ra = float((resp.headers or {}).get("retry-after"))
        except Exception: ra = None
        return max(0.5, ra if ra is not None else min(30.0, 1.5 * (2 ** attempt)))
    for attempt in range(sess.max_retries + 1):
        streamed = False
        try:
            with requests.post(url, headers=headers, json=payload, stream=sess.stream,
                               timeout=(sess.connect_timeout, sess.read_timeout), proxies=sess.proxies, verify=sess.verify) as r:
                if r.status_code >= 400:
                    if r.status_code in _RETRYABLE and attempt < sess.max_retries:
                        d = _delay(r, attempt)
                        print(f"[LLM Retry] HTTP {r.status_code}, retry in {d:.1f}s ({attempt+1}/{sess.max_retries+1})")
                        time.sleep(d); continue
                    try: body = r.text.strip()[:500]
                    except Exception: body = ""
                    err = f"!!!Error: HTTP {r.status_code}" + (f": {body}" if body else "")
                    yield err; return [{"type": "text", "text": err}]
                gen = parse_fn(r)
                try:
                    while True: streamed = True; yield next(gen)
                except StopIteration as e:
                    if not e.value and not streamed: raise requests.ConnectionError("empty response")
                    return e.value or []
        except (requests.Timeout, requests.ConnectionError) as e:
            err = f"!!!Error: {type(e).__name__}"
            if attempt < sess.max_retries:
                d = _delay(None, attempt)
                print(f"[LLM Retry] {type(e).__name__}, retry in {d:.1f}s ({attempt+1}/{sess.max_retries+1})")
                yield err; time.sleep(d); continue
            yield err; return [{"type": "text", "text": err}]
        except Exception as e:
            err = f"\n\n[!!! 流异常中断 {type(e).__name__}: {e} !!!]" if streamed else f"!!!Error: {type(e).__name__}: {e}"
            yield err; return [{"type": "text", "text": err}]

def _write_llm_log(label, content, log_path=None):
    if not log_path:
        log_path = str(TEMP / 'model_responses' / f'model_responses_{os.getpid()}.txt')
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(log_path, 'a', encoding='utf-8', errors='replace') as f:
        f.write(f"=== {label} === {ts}\n{content}\n\n")

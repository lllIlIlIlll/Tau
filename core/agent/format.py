"""输出整形工具：loop 与 handler 共用的纯函数。
逐字搬自原 core/agent_loop.py（行为零变化），不依赖 agent 包内其它模块。"""
import json, os, re


def json_default(o):
    return list(o) if isinstance(o, set) else str(o)


def get_pretty_json(data):
    if isinstance(data, dict) and "script" in data:
        data = data.copy(); data["script"] = data["script"].replace("; ", ";\n  ")
    return json.dumps(data, indent=2, ensure_ascii=False).replace('\\n', '\n')


def _clean_content(text):
    if not text: return ''
    def _shrink_code(m):
        lines = m.group(0).split('\n')
        lang = lines[0].replace('```','').strip()
        body = [l for l in lines[1:-1] if l.strip()]
        if len(body) <= 6: return m.group(0)
        preview = '\n'.join(body[:5])
        return f'```{lang}\n{preview}\n  ... ({len(body)} lines)\n```'
    text = re.sub(r'```[\s\S]*?```', _shrink_code, text)
    for p, repl in ((r'<file_content>[\s\S]*?</file_content>', ''), (r'<tool_(?:use|call)>[\s\S]*?</tool_(?:use|call)>', ''), (r'(\r?\n){3,}', '\n\n')):
        text = re.sub(p, repl, text)
    return text.strip()


def _compact_tool_args(name, args):
    a = {k: v for k, v in args.items() if k != '_index'}
    for k in ('path',):
        if k in a: a[k] = os.path.basename(a[k])
    if name == 'update_working_checkpoint': s = a.get('key_info', ''); return (s[:60]+'...') if len(s)>60 else s
    if name == 'ask_user':
        q = str(a.get('question', ''))
        cs = a.get('candidates') or []
        if cs: q += '\ncandidates:\n' + '\n'.join(f'- {c}' for c in cs)
        return q
    s = json.dumps(a, ensure_ascii=False); return (s[:120]+'...') if len(s)>120 else s

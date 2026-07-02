import os, sys, threading, queue, time, json, re, random, locale
from ..llm.keys import reload_taukeys
from ..llm.clients import ToolClient, NativeToolClient, MixinSession, resolve_client
from ..llm.providers.openai import LLMSession, NativeOAISession
from ..llm.providers.claude import ClaudeSession, NativeClaudeSession
from .loop import agent_runner_loop
from .handler import TauHandler
from ..tools.utils import smart_format, get_global_memory, format_error, consume_file
from ..paths import TAU_HOME, MEMORY, ASSETS, TEMP

# ----------------------------------------------------------------------------
# 模块级常量（纯计算，零副作用）
# ----------------------------------------------------------------------------
script_dir = str(TAU_HOME / "core")

# 幂等保护 —— bootstrap() 多重调用安全
_bootstrapped = False

# ----------------------------------------------------------------------------
# bootstrap() —— 显式初始化入口
# ----------------------------------------------------------------------------
def _init_streams():
    """stdout/stderr 兜底与编码修复（pythonw / subprocess 场景）。"""
    for name in ('stdout', 'stderr'):
        s = getattr(sys, name)
        if s is None: setattr(sys, name, open(os.devnull, 'w'))
        elif hasattr(s, 'reconfigure'): s.reconfigure(errors='replace')

def _init_lang():
    """GA_LANG 默认值（locale 探测）。必须在任何读 os.environ.get('GA_LANG') 的代码之前。"""
    is_zh = any(k in (locale.getlocale()[0] or '').lower() for k in ('zh', 'chinese'))
    os.environ.setdefault('GA_LANG', 'zh' if is_zh else 'en')

def _init_memory():
    """memory dir + global_mem.txt + global_mem_insight.txt 种子文件。"""
    MEMORY.mkdir(parents=True, exist_ok=True)
    mem = MEMORY / 'global_mem.txt'
    if not mem.exists(): mem.write_text('# [Global Memory - L2]\n', encoding='utf-8')
    insight = MEMORY / 'global_mem_insight.txt'
    if not insight.exists():
        t = ASSETS / f'template/global_mem_insight_template{lang_suffix()}.txt'
        insight.write_text(t.read_text(encoding='utf-8') if t.exists() else '', encoding='utf-8')

def _init_cdp():
    """TMWebDriver CDP config.js 初始化。失败仅警告（按失败半径）。"""
    cfg = TAU_HOME / 'TMWebDriver/tmwd_cdp_bridge/config.js'
    if cfg.exists(): return
    try:
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(f"const TID = '__ljq_{hex(random.randint(0, 99999999))[2:8]}';", encoding='utf-8')
    except OSError as e:
        print(f'[WARN] CDP config init failed: {e} — advanced web features (tmwebdriver) will be unavailable.')

def _init_plugins():
    """插件发现与加载。插件不存在则静默（琐碎），插件错误则 fail loud。"""
    try:
        from plugins.hooks import discover_and_load
    except ImportError:
        return
    discover_and_load()

def _placeholder_for_pr3():
    """占位：默认 tool schema 加载的具体策略待后续重构接管。

    当前默认加载已迁到 Tau.__init__ 末尾（一次性填入 self.tools_schema）。
    此函数保留为可显式 raise 的守门,避免被静默跳过；后续重构若决定
    纳入 bootstrap 副作用,请在此处实现或删除本占位。
    """
    raise NotImplementedError("placeholder_for_pr3: default tool schema load not yet wired")

def bootstrap():
    """显式初始化 runtime 模块副作用。幂等。

    调用点：Tau.__init__ / main()（CLI 入口，覆盖 task / reflect / 交互三模式）。
    副作用清单（5 个 _init_xxx）：
      streams / lang / memory / cdp / plugins
      注：handler.py 内同类副作用不在本函数管辖范围，待 handler.py 重构时统一处理。
      注：默认 tool schema 加载已迁到 Tau.__init__ 末尾，不在 bootstrap 副作用内。
    """
    global _bootstrapped
    if _bootstrapped: return
    # 注意：lang 必须早于所有读 GA_LANG 的代码（memory / schema / sys_prompt 都依赖）。
    _init_streams()
    _init_lang()
    _init_memory()
    _init_cdp()
    _init_plugins()
    _bootstrapped = True

# ----------------------------------------------------------------------------
# 公开 API
# ----------------------------------------------------------------------------
def lang_suffix():
    """基于当前 GA_LANG 返回 `_en` 或空串。函数形式而非模块级缓存（GA_LANG 在 bootstrap 时设置）。"""
    return '_en' if os.environ.get('GA_LANG', '') == 'en' else ''

def load_tool_schema(suffix=''):
    """加载 tools_schema{suffix}.json 并返回 dict（不再写入模块全局 TOOLS_SCHEMA）。

    PR-2 行为变更：从此函数返回值，不再有 side effect（除读文件外）。
    调用方：Tau.__init__ 用 self.tools_schema = load_tool_schema() 缓存到实例。
    """
    TS = open(str(ASSETS / f'tools_schema{suffix}.json'), 'r', encoding='utf-8').read()
    return json.loads(TS if os.name == 'nt' else TS.replace('powershell', 'bash'))

def get_system_prompt():
    with open(str(ASSETS / f'prompts/sys_prompt{lang_suffix()}.txt'), 'r', encoding='utf-8') as f: prompt = f.read()
    prompt += f"\nToday: {time.strftime('%Y-%m-%d %a')}\n"
    prompt += get_global_memory()
    return prompt

class Tau:
    def __init__(self):
        bootstrap()  # 模块副作用显式化（幂等）—— 必须在 self.tools_schema 填充前
        os.makedirs(str(TEMP), exist_ok=True)
        self.lock = threading.Lock()
        self.task_dir = None
        self.history = []; self.handler = None;
        self.task_queue = queue.Queue()
        self.is_running = False; self.stop_sig = False; self.llm_no = 0;
        self.inc_out = False; self.verbose = True; self.show_mode = 'text'
        self.peer_hint = True
        self.log_path = str(TEMP / f'model_responses/model_responses_{int(time.time()*1e6)%1000000:06d}.txt')
        self.load_llm_sessions()
        # PR-2 行为变更：load_tool_schema 不再写全局 TOOLS_SCHEMA，改为缓存到实例属性。
        # PR-3：suffix 由 llmclient.backend.schema_suffix 提供（resolve_session 时已写入，
        #       兼容老配置无 schema_suffix 字段时按 _LEGACY_CN_MODELS 兜底）。
        self.tools_schema = load_tool_schema(getattr(self.llmclient.backend, 'schema_suffix', ''))

    def load_llm_sessions(self):
        taukeys, changed = reload_taukeys()
        if not changed and hasattr(self, 'llmclients'): return
        try: oldhistory = self.llmclient.backend.history
        except Exception: oldhistory = None
        llm_sessions = []
        for k, cfg in taukeys.items():
            if not any(x in k for x in ['api', 'config', 'cookie']): continue
            try:
                if 'mixin' in k: llm_sessions += [{'mixin_cfg': cfg}]
                elif c := resolve_client(k): llm_sessions += [c]
            except Exception as e: print(f'[WARN] skip LLM config {k}: {format_error(e)}')
        for i, s in enumerate(llm_sessions):
            if isinstance(s, dict) and 'mixin_cfg' in s:
                try:
                    mixin = MixinSession(llm_sessions, s['mixin_cfg'])
                    if isinstance(mixin._sessions[0], (NativeClaudeSession, NativeOAISession)): llm_sessions[i] = NativeToolClient(mixin)
                    else: llm_sessions[i] = ToolClient(mixin)
                except Exception as e: print(f'\n\n\n[ERROR] Failed to init MixinSession with cfg {s["mixin_cfg"]}: {e}!!!\n\n')
        if not llm_sessions: raise RuntimeError('No valid LLM config loaded from .tau/taukey.py — check api/config/cookie entries (run `tau configure`)')
        self.llmclients = llm_sessions
        self.llmclient = self.llmclients[self.llm_no%len(self.llmclients)]
        if oldhistory: self.llmclient.backend.history = oldhistory
    
    def next_llm(self, n=-1):
        self.load_llm_sessions()
        self.llm_no = ((self.llm_no + 1) if n < 0 else n) % len(self.llmclients)
        lastc = self.llmclient
        self.llmclient = self.llmclients[self.llm_no]
        try: self.llmclient.backend.history = lastc.backend.history
        except Exception: raise Exception('[ERROR] BAD Mixin config: Check your .tau/taukey.py (run `tau configure`)')
        self.llmclient.last_tools = ''
        # PR-3：suffix 一律从 backend 读（resolve_session 时已设置，兼容老配置走 _legacy_schema_suffix 兜底）。
        self.tools_schema = load_tool_schema(getattr(self.llmclient.backend, 'schema_suffix', ''))
    def list_llms(self): 
        self.load_llm_sessions()
        return [(i, self.get_llm_name(b), i == self.llm_no) for i, b in enumerate(self.llmclients)]
    def get_llm_name(self, b=None, model=False):
        b = self.llmclient if b is None else b
        if isinstance(b, dict): return 'BADCONFIG_MIXIN'
        if model: return b.backend.model.lower()
        return f"{type(b.backend).__name__}/{b.backend.name}"

    def abort(self):
        if not self.is_running: return
        print('Abort current task...')
        self.stop_sig = True
        if self.handler is not None: self.handler.code_stop_signal.append(1)
            
    def put_task(self, query, source="user", images=None):
        display_queue = queue.Queue()
        self.task_queue.put({"query": query, "source": source, "images": images or [], "output": display_queue})
        return display_queue

    # i know it is dangerous, but raw_query is dangerous enough it doesn't enlarge
    def _handle_slash_cmd(self, raw_query, display_queue):
        if not raw_query.startswith('/'): return raw_query
        if _sm := re.match(r'/session\.(\w+)=(.*)', raw_query.strip()):
            k, v = _sm.group(1), _sm.group(2)
            vfile = str(TEMP / v)
            if os.path.isfile(vfile): v = open(vfile, encoding='utf-8').read().strip()
            try: v = json.loads(v)  # cover number parsing
            except (json.JSONDecodeError, ValueError): pass
            setattr(self.llmclient.backend, k, v)
            display_queue.put({'done': smart_format(f"✅ session.{k} = {repr(v)}", max_str_len=500), 'source': 'system'})
            return None
        if raw_query.strip() == '/resume':
            return r'帮我看看最近有哪些会话可以恢复。读model_responses/目录，按修改时间取最近10个文件，从每个文件里找最后一个<history>...</history>块，用一句话总结每个会话在聊什么，列表给我选。注意读文件后要把字面的\n替换成真换行才能正确匹配。'
        return raw_query

    def run(self):
        while True:
            task = self.task_queue.get()
            raw_query, source, display_queue = task["query"], task["source"], task["output"]
            raw_query = self._handle_slash_cmd(raw_query, display_queue)
            if raw_query is None:
                self.task_queue.task_done(); continue
            self.is_running = True
            rquery = smart_format(raw_query.replace('\n', ' '), max_str_len=200)
            self.history.append(f"[USER]: {rquery}")
            
            sys_prompt = get_system_prompt() + getattr(self.llmclient.backend, 'extra_sys_prompt', '')
            if self.peer_hint: sys_prompt += f"\n[Peer] 用户提及其他会话/后台任务状态时: temp/model_responses/ (只找近期修改的文件尾部)\n"
            handler = TauHandler(self, self.history, str(TEMP))
            if self.handler and 'key_info' in self.handler.working: 
                ki = re.sub(r'\n\[SYSTEM\] 此为.*?工作记忆[。\n]*', '', self.handler.working['key_info'])  # 去旧
                handler.working['key_info'] = ki
                handler.working['passed_sessions'] = ps = self.handler.working.get('passed_sessions', 0) + 1
                if ps > 0: handler.working['key_info'] += f'\n[SYSTEM] 此为 {ps} 个对话前设置的key_info，若已在新任务，先更新或清除工作记忆。\n'
            self.handler = handler  # although new handler, the **full** history is in llmclient, so it is full history!
            self.llmclient.log_path = self.log_path
            gen = agent_runner_loop(self.llmclient, sys_prompt, raw_query, handler, self.tools_schema,
                                    max_turns=80, verbose=self.verbose, yield_info=True)
            try:
                full_resp = ""; last_pos = 0; curr_turn = 0; turn_resps = []
                for chunk in gen:
                    if consume_file(self.task_dir, '_stop'): self.abort() 
                    if self.stop_sig: break
                    if isinstance(chunk, dict) and 'turn' in chunk: 
                        curr_turn = chunk['turn']; turn_resps.append(''); continue
                    full_resp += chunk;  turn_resps[-1] += chunk
                    if len(full_resp) - last_pos > 30 or 'LLM Running' in chunk:
                        display_queue.put({'next': full_resp[last_pos:] if self.inc_out else full_resp, 
                                           'source': source, 'turn': curr_turn, 'outputs': turn_resps[-2:]})
                        last_pos = len(full_resp)
                if self.inc_out and last_pos < len(full_resp): display_queue.put({'next': full_resp[last_pos:], 'source': source, 
                                                                                  'turn': curr_turn, 'outputs': turn_resps[-2:]})
                display_queue.put({'done': full_resp, 'source': source, 'turn': curr_turn, 'outputs': turn_resps.copy()})
                self.history = handler.history_info
            except Exception as e:
                print(f"Backend Error: {format_error(e)}")
                display_queue.put({'done': full_resp + f'\n```\n{format_error(e)}\n```', 'source': source, 'turn': curr_turn, 'outputs': turn_resps.copy()})
            finally:
                if self.stop_sig: print('User aborted the task.')
                self.is_running = self.stop_sig = False
                self.task_queue.task_done()
                if self.handler is not None: self.handler.code_stop_signal.append(1)
def main():
    bootstrap()  # CLI 入口：覆盖 task / reflect / 交互三模式，必须先做（幂等）
    import argparse
    from datetime import datetime
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', metavar='IODIR', help='一次性任务模式(文件IO)')
    parser.add_argument('--reflect', metavar='SCRIPT', help='反射模式：加载监控脚本，check()触发时发任务')
    parser.add_argument('--input', help='prompt')
    parser.add_argument('--llm_no', type=int, default=0)
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--nobg', action='store_true')
    args, _unknown = parser.parse_known_args()
    _reflect_args = dict(zip([k.lstrip('-') for k in _unknown[::2]], _unknown[1::2])) if _unknown else {}

    if args.task and not args.nobg:
        import subprocess, platform
        cmd = [sys.executable, os.path.abspath(__file__)] + [a for a in sys.argv[1:]] + ['--nobg']
        d = str(TEMP / args.task); os.makedirs(d, exist_ok=True)
        p = subprocess.Popen(cmd, cwd=script_dir,
            creationflags=0x08000000 if platform.system() == 'Windows' else 0,
            stdout=open(os.path.join(d, 'stdout.log'), 'w', encoding='utf-8'),
            stderr=open(os.path.join(d, 'stderr.log'), 'w', encoding='utf-8'))
        print(p.pid); sys.exit(0)

    agent = Tau()
    agent.next_llm(args.llm_no)
    agent.verbose = args.verbose
    threading.Thread(target=agent.run, daemon=True).start()

    if args.task:
        agent.peer_hint = False
        agent.task_dir = d = str(TEMP / args.task); nround = ''
        infile = os.path.join(d, 'input.txt')
        if args.input:
            os.makedirs(d, exist_ok=True)
            import glob; [os.remove(f) for f in glob.glob(os.path.join(d, 'output*.txt'))]
            with open(infile, 'w', encoding='utf-8') as f: f.write(args.input)
        if (fh := consume_file(d, '_history.json')): agent.llmclient.backend.history = json.loads(fh)
        with open(infile, encoding='utf-8') as f: raw = f.read()
        while True:
            dq = agent.put_task(raw, source='task')
            while 'done' not in (item := dq.get(timeout=300)): 
                if 'next' in item and random.random() < 0.95:  # 概率写一次中间结果
                    with open(f'{d}/output{nround}.txt', 'w', encoding='utf-8') as f: f.write(item.get('next', ''))
            with open(f'{d}/output{nround}.txt', 'w', encoding='utf-8') as f: f.write(item['done'] + '\n\n[ROUND END]\n')
            consume_file(d, '_stop')  # 已经成功停下来了，避免打断下次reply
            for _ in range(300):  # 等reply.txt，10分钟超时
                time.sleep(2)
                if (raw := consume_file(d, 'reply.txt')): break
            else: break
            nround = nround + 1 if isinstance(nround, int) else 1
    elif args.reflect:
        agent.peer_hint = False
        import importlib.util
        spec = importlib.util.spec_from_file_location('reflect_script', args.reflect)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        if hasattr(mod, 'init'): mod.init(_reflect_args)
        _mt = os.path.getmtime(args.reflect)
        print(f'[Reflect] loaded {args.reflect}' + (f' args={_reflect_args}' if _reflect_args else ''))
        while True:
            if os.path.getmtime(args.reflect) != _mt:
                try:
                    spec.loader.exec_module(mod); _mt = os.path.getmtime(args.reflect)
                    if hasattr(mod, 'init'): mod.init(_reflect_args)
                    print('[Reflect] reloaded')
                except Exception as e: print(f'[Reflect] reload error: {e}')
            time.sleep(getattr(mod, 'INTERVAL', 5))
            try: task = mod.check()
            except Exception as e: 
                print(f'[Reflect] check() error: {e}'); continue
            if task and task == '/exit': break
            if task is None: continue
            print(f'[Reflect] triggered: {task[:80]}')
            dq = agent.put_task(task, source='reflect')
            try:
                while 'done' not in (item := dq.get(timeout=180)): pass
                result = item['done']
                print(result)
            except Exception as e:
                if getattr(mod, 'ONCE', False): raise
                print(f'[Reflect] drain error: {e}'); result = f'[ERROR] {e}'
            log_dir = str(TEMP / 'reflect_logs'); os.makedirs(log_dir, exist_ok=True)
            script_name = os.path.splitext(os.path.basename(args.reflect))[0]
            open(os.path.join(log_dir, f'{script_name}_{datetime.now():%Y-%m-%d}.log'), 'a', encoding='utf-8').write(f'[{datetime.now():%m-%d %H:%M}]\n{result}\n\n')
            if (on_done := getattr(mod, 'on_done', None)):
                try: on_done(result)
                except Exception as e: print(f'[Reflect] on_done error: {e}')
            if getattr(mod, 'ONCE', False): print('[Reflect] ONCE=True, exiting.'); break
    else:
        try: import readline
        except Exception: pass
        agent.inc_out = True
        if sys.stdout.isatty():
            try: model = agent.get_llm_name(model=True) or '?'
            except Exception: model = '?'
            try:
                sys.stdout.write(f'\x1b[92m✦\x1b[0m \x1b[1mTau\x1b[0m '
                                 f'\x1b[90m· cli · model:\x1b[0m {model}\n')
                sys.stdout.flush()
            except Exception: pass
        while True:
            q = input('> ').strip()
            if not q: continue
            try:
                dq = agent.put_task(q, source='user')
                while True:
                    item = dq.get()
                    if 'next' in item: print(item['next'], end='', flush=True)
                    if 'done' in item: print(); break
            except KeyboardInterrupt:
                agent.abort()
                print('\n[Interrupted]')


if __name__ == '__main__':
    main()

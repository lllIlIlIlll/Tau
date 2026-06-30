# Subagent 评审 TODO 最佳实践模板 (L8)

> 目的: 让未来主 agent 稳定地召唤 subagent 评审 TODO, 避免 3 大坑。
> 触发: 任何需要第三方可信评审 TODO.txt 的场景。
> 维护: 召唤失败/出新坑时, 在 §5 增补一条。
> 落盘: 2026-06-18 (R4 partial, 模板已落盘, 实测待 L8 用户批后跑)

---

## 1. 启动 subagent (最小命令)

```bash
cd <CodeRoot>  # 含 taumain.py 的目录
TASK=review_todo_$(date +%Y%m%d)
mkdir -p temp/$TASK
cat > temp/$TASK/input.txt <<EOF
评审 temp/TODO.txt 的 [ ] TODO。读 memory/global_mem.txt + memory/autonomous_operation_sop/task_planning.md 了解环境。逐条 1-10 评分, 输出 temp/$TASK/review.md >=5KB, 7+ 节。
EOF
python taumain.py --task $TASK --llm_no 0
```

参数:
- `--task` = 子目录名, 唯一标识 (避免 §5 坑1 覆盖)
- `--input` = 短文本, 启动时自动建目录+清旧 output+写 input.txt
- `--llm_no N` = 多 LLM 并行编号, 单 subagent 跑 0

---

## 2. input.txt 样板 (TODO 评审主场景)

```
# TODO 评审任务 (单 subagent)

## 输入
- TODO 路径: <绝对路径>/temp/TODO.txt
- 记忆库根: <绝对路径>/memory/

## 任务
1. 读 TODO.txt, 列出所有 [ ] / [x] / [BLOCKED]
2. 读 L0 META-SOP + L1 insight + L2 global_mem.txt
3. 对每条 [ ] 给出 1-10 评分 + 1-2 句理由
4. 标注每条 [ ] 的显式依赖 (其他 TODO/外部权限/用户授权)
5. 输出 review.md >=5KB, 7+ 节
6. 给主 agent 推荐 TOP3 排序 + 删除/合并建议

## 硬约束
- ❌ 不给先验分数或诱导
- ❌ 不评如何实现, 只评值不值得 + 多复杂
- ✅ 引用具体 L2/L3 文件名作为依据
- ✅ 评审产物 = temp/<task_name>/review.md
```

---

## 3. review.md 输出格式 (7+ 节)

参考 2026-06-16 真实范式 `temp/review.md` (245 行, 8 节):

| § | 节标题 | 最低行数 | 内容 |
|---|---|---|---|
| 一 | 关键事实发现 | 5 | 读 L0/L1/L2 后的 3-5 条硬约束/事实 |
| 二 | JSON 评分 | 10 | 每条 TODO 一个 {name,score,deps,value,complexity,reversible} |
| 三 | 逐条详细理由 | 50 | 每条 2-5 句 (引用 L2/L3) |
| 四 | 低分项替换方案 | 20 | score<6 的各给一替换 |
| 五 | 依赖悬空/拆分 | 20 | 不拆也说无需拆的理由 |
| 六 | 主 agent 推荐排序 | 5 | TOP3 + 删除/合并建议 |
| 七 | TOP1 执行入口 | 30 | 步骤/产物/验收/避坑 |
| 八 | 评审结论 | 3 | 一句话 + 可不可执行判断 |

**硬下限**: 5KB / 200 行 / 7+ 节 (一-七); 实际评审 1.5x 富余 ≈ 350 行 ≈ 7KB。

---

## 4. 产物验证 (主 agent 收尾必跑)

```bash
REVIEW=temp/$TASK/review.md
[ -f "$REVIEW" ] || { echo "❌ review.md 不存在"; exit 1; }
SIZE=$(wc -c < "$REVIEW")
[ "$SIZE" -ge 5120 ] || { echo "❌ < 5KB ($SIZE B)"; exit 1; }
for sec in "一、" "二、" "三、" "四、" "五、" "六、" "七、"; do
  grep -q "^## $sec" "$REVIEW" || { echo "❌ 缺节: ## $sec"; exit 1; }
done
STDOUT=temp/$TASK/stdout.log
[ -f "$STDOUT" ] && grep -qi "output.*覆盖\|overwrit" "$STDOUT" && { echo "❌ 覆盖警告"; exit 1; }
TODO_C=$(grep -c "^\\[ \\]" temp/TODO.txt)
JSON_C=$(grep -c '"name":' "$REVIEW")
[ "$JSON_C" -ge "$TODO_C" ] || { echo "❌ 评分缺"; exit 1; }
echo "✅ 验收通过"
```

---

## 5. 三大坑 (L8 验收硬要求, 召前必读)

### 坑 1: output 覆盖 (高频)
**症状**: 启动新 subagent 后, 旧任务 output.txt 被静默清空
**规避**:
1. 每个评审用独立 task_name (含日期戳)
2. 启动前 `ls temp/{task}/` 必须只有 input.txt, 有别文件先 mv 到 backup/
3. 启动 5s 内立即 `cat temp/{task}/output.txt` 确认有内容
4. 旧评审归档: `tar czf temp/archive/review_$(date +%Y%m%d).tar.gz temp/review_*/`

### 坑 2: reply 节奏 10min 超时 (中频)
**症状**: subagent 写完 output 等主 agent reply, 10min 无 reply 自动退出
**规避**:
1. 每 2-5min 轮询一次 output.txt, 看到 [ROUND END] 立刻写 reply.txt
2. 不复述 subagent 结论再问, 直接给下一步
3. 复杂任务用 fork 模式 (code_run inline_eval=True) 让 subagent 继承上下文
4. >30min 任务拆成 pipeline

### 坑 3: fallback 转自评 (必堵)
**症状**: subagent 启动失败 (LLM 配额/网络/cwd 错), 主 agent 偷懒自己评
**SOP 硬约束**: task_planning.md step 7 "TODO 必须经 subagent 评审, 不允许自评, 未经评审的 TODO 不可执行"
**规避**:
1. 失败重试 >= 3 次 (换 --llm_no, 加 timeout, 简化 input)
2. 降级也必须 subagent 跑 (用 subagent.md 场景 2 Map 模式验证环境)
3. 实在不行 -> 标 [BLOCKED] 写明阻塞原因, 不进入执行序列

---

## 6. 端到端示例 (评审当前 TODO.txt)

```bash
cd <CodeRoot>; TASK=review_todo_$(date +%Y%m%d)
mkdir -p temp/$TASK
cat > temp/$TASK/input.txt <<EOF
评审 temp/TODO.txt 的 [ ] TODO。读 memory/global_mem.txt + memory/autonomous_operation_sop/task_planning.md。逐条 1-10 评分 + 理由, 输出 temp/$TASK/review.md >=5KB 7+ 节。参考范式: temp/review.md (2026-06-16, 245行, 8节, 6 TODO)。
EOF
python taumain.py --task $TASK --llm_no 0
# 轮询: while ! grep -q "review.md.*写入" temp/$TASK/output.txt; do sleep 180; done
# 验收: bash memory/autonomous_operation_sop/subagent_review_template_audit.sh $TASK
# 落分: 读 review.md §六"推荐排序", 删低分, 重排 TODO.txt
```

---

## 7. 维护

- 新坑 -> §5 增补一条, 标日期
- 新场景 input 模板 -> §2 增补一节
- real-world 评审 -> §3 加一行 (日期/路径/行数/节数/评分数)
- 审计脚本自动化 -> §4 bash 落盘为 `subagent_review_template_audit.sh` (R4 计划内未完)

**R4 落盘**: 2026-06-18 (R4 partial)
**关联**: TODO L8 (本任务) / TODO 3c (待 L8 用户批后实测)

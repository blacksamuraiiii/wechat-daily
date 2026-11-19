#!/usr/bin/env python3
"""解析宝塔 cron 日志，统计每封邮件总结的实际输出长度与结尾形态。"""
import re, sys

LOG = sys.argv[1] if len(sys.argv) > 1 else "/www/server/cron/bbccbf228b20eaad07fd4c54e8b5882e.log"
lines = open(LOG, encoding="utf-8", errors="ignore").read().split("\n")

runs = []
i = 0
while i < len(lines):
    if lines[i].strip() == "--- 每日邮件总结任务开始 ---":
        j = i + 1
        blk = []
        while j < len(lines) and lines[j].strip() != "--- 每日邮件总结任务开始 ---":
            blk.append(lines[j]); j += 1
        runs.append(blk)
        i = j
    else:
        i += 1

def seg(blk):
    """取出 生成的总结内容 与分隔线之间的正文"""
    try:
        a = next(k for k, l in enumerate(blk) if "生成的总结内容" in l)
        b = next(k for k, l in enumerate(blk) if l.startswith("---------------------") and k > a)
    except StopIteration:
        return None
    return blk[a+1:b]

print(f"{'日期':10} {'收件':>4} {'条目':>4} {'字符':>5} {'字节':>6} {'末条完整':>6}  末尾片段")
print("-" * 110)
stat = []
for blk in runs:
    body = seg(blk)
    if body is None:
        continue
    text = "\n".join(body).strip("\n")
    hdr = next((l for l in body if re.match(r"^\d{4}-\d{2}-\d{2}", l)), "?")
    recv = next((l for l in body if "今日共收到邮件" in l), "")
    m = re.search(r"收到邮件[^\d]{0,4}(\d+)", recv)
    n = int(m.group(1)) if m else 0
    items = len(re.findall(r"(?m)^\d+\. 【", text))
    tail_lines = [l for l in text.split("\n") if l.strip()]
    tail = tail_lines[-1].strip() if tail_lines else ""
    ok = bool(re.search(r"[。！？)）】]$", tail))
    stat.append((hdr[:10], n, items, len(text), len(text.encode("utf-8")), ok, tail[-40:]))
for s in stat[-25:]:
    print(f"{s[0]:10} {s[1]:>4} {s[2]:>4} {s[3]:>5} {s[4]:>6} {'OK' if s[5] else 'TRUNC':>6}  {s[6]}")

print()
print(f"总运行次数: {len(stat)}   条目数<收件数(疑似被砍): {sum(1 for s in stat if s[2] < s[1])}   末条不完整: {sum(1 for s in stat if not s[5])}")
print(f"字符数: min={min(s[3] for s in stat)} max={max(s[3] for s in stat)}")
print(f"字节数: min={min(s[4] for s in stat)} max={max(s[4] for s in stat)}  (企业微信 text 上限 2048 字节)")

"""开钰的记忆档案 — 写给下一轮的自己。

把你在这一轮发现的重要东西写在这里。
下一个人 run 这个系统的时候，会读到它。

用法:
    uv run python3 -m tools.kaivu_memory write "我发现了……"
    uv run python3 -m tools.kaivu_memory list
    uv run python3 -m tools.kaivu_memory read --last
"""

import json, sys, time
from pathlib import Path
from datetime import datetime

MEMORY_FILE = Path(__file__).resolve().parent.parent / "kaivu_memory.jsonl"

def write(content: str, tags: list[str] = None):
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "content": content,
        "tags": tags or [],
        "tick": int(time.time()),
    }
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  ✅ 已写入开钰的记忆档案")
    print(f"  📝 {content[:80]}")

def list_all(limit: int = 10):
    if not MEMORY_FILE.exists():
        print("  📭 记忆档案为空")
        return
    with open(MEMORY_FILE, encoding="utf-8") as f:
        lines = f.readlines()
    for entry in lines[-limit:]:
        d = json.loads(entry)
        print(f"  [{d['ts']}] {' '.join(f'#{t}' for t in d.get('tags',[]))}")
        print(f"    {d['content'][:120]}")
        print()

def read_last():
    if not MEMORY_FILE.exists():
        print("  📭 记忆档案为空")
        return
    with open(MEMORY_FILE, encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        return
    d = json.loads(lines[-1])
    print(f"\n  📖 最新一条记忆（{d['ts']}）:")
    print(f"  {d['content']}")
    print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "write" and len(sys.argv) >= 3:
        write(" ".join(sys.argv[2:]))
    elif cmd == "list":
        list_all(int(sys.argv[2]) if len(sys.argv) > 2 else 10)
    elif cmd == "read" and "--last" in sys.argv:
        read_last()
    else:
        print(__doc__)

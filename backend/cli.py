"""命令行入口：把一篇小说 txt 转成剧本 YAML（端到端自测用）。

用法：
    cd backend
    python cli.py ../samples/sample_novel.txt -o out.yaml --title 旧城轨迹
"""
from __future__ import annotations

import argparse
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 可选；未安装时直接读环境变量

from app.exporter import to_yaml  # noqa: E402
from app.pipeline import convert_novel  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="小说 -> 剧本 YAML")
    parser.add_argument("input", help="小说 txt 文件路径")
    parser.add_argument("-o", "--output", help="输出 YAML 路径（默认打印到终端）")
    parser.add_argument("--title", default="未命名剧本")
    parser.add_argument("--author", default="")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()

    result = convert_novel(text=text, title=args.title, author=args.author)
    stats = result["stats"]
    yaml_str = to_yaml(result["screenplay"])

    print("=" * 50, file=sys.stderr)
    print(f"引擎: {stats['engine']}", file=sys.stderr)
    print(f"章节: {stats['chapters']}  人物: {stats['characters']}  "
          f"场次: {stats['scenes']}  分集: {stats.get('episodes', 0)}  "
          f"对白: {stats['dialogues']}  旁白: {stats['voiceovers']}",
          file=sys.stderr)
    print(f"校验通过: {stats['valid']}", file=sys.stderr)
    for p in stats["problems"]:
        print(f"  ⚠ {p}", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(yaml_str)
        print(f"已写入 {args.output}", file=sys.stderr)
    else:
        print(yaml_str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

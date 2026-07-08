#!/usr/bin/env python3
"""统计 links[] 中每条边的 link 属性字段存在性与值分布。

统计维度：
- LEFTPORT / RIGHTPORT / CLASSNAME 字段覆盖率
- LEFTPORT / RIGHTPORT 值分布：去除数字后缀聚合（GigabitEthernet0/0/0 → GigabitEthernet）
- CLASSNAME 的值类别分布
- 按 split 汇总
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_DATASET_ROOT = Path("datasets")
DEFAULT_OUTPUT_DIR = Path("statistics")
DEFAULT_PROGRESS_INTERVAL = 50

# link 内待检查的字段
LINK_FIELDS = ["LEFTPORT", "RIGHTPORT", "CLASSNAME"]

# 需要去除数字后缀的端口字段
PORT_FIELDS = {"LEFTPORT", "RIGHTPORT"}

FIELD_LABELS = {
    "LEFTPORT": "左端口 (LEFTPORT)",
    "RIGHTPORT": "右端口 (RIGHTPORT)",
    "CLASSNAME": "链路类型 (CLASSNAME)",
}


def strip_port_number(value: str) -> str:
    """去除端口名中数字及之后的部分。

    GigabitEthernet0/0/0 → GigabitEthernet
    MultiGE0/0/0 → MultiGE
    Vlanif1 → Vlanif
    """
    return re.sub(r"\d.*$", "", value)


def iter_json_files(dataset_root: Path, splits: Iterable[str]) -> Iterable[Tuple[str, Path]]:
    """按 split 递归枚举 JSON 文件。"""
    for split in splits:
        split_dir = dataset_root / split
        if not split_dir.exists():
            continue
        for path in sorted(split_dir.rglob("*.json")):
            if path.is_file():
                yield split, path


def list_split_json_files(dataset_root: Path, split: str) -> List[Path]:
    """列出单个 split 下的 JSON 文件。"""
    return [path for _, path in iter_json_files(dataset_root, [split])]


def load_graph(path: Path) -> Tuple[Dict[str, Any] | None, str]:
    """读取一张图。"""
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, str(exc)
    if not isinstance(graph, dict):
        return None, f"top-level JSON type is {type(graph).__name__}, expected object"
    return graph, ""


def analyze_graph(graph: Dict[str, Any]) -> Tuple[Counter, Counter, Counter]:
    """分析一张图中 link 字段的存在性与值分布。

    返回:
    - presence_counter: {field_name: 该字段存在的边数}
    - value_counters: {field_name: Counter(值 → 出现次数)}
    - 缺失详情列表
    """
    presence_counter: Counter = Counter()
    value_counters: Dict[str, Counter] = {field: Counter() for field in LINK_FIELDS}
    missing_details: List[Dict[str, Any]] = []

    links = graph.get("links")
    if not isinstance(links, list):
        return presence_counter, value_counters, missing_details

    for link_index, link_item in enumerate(links):
        if not isinstance(link_item, dict):
            continue
        link = link_item.get("link")
        if not isinstance(link, dict):
            # link 字段不存在或不是 dict，所有子字段都缺失
            missing_fields = LINK_FIELDS.copy()
            missing_details.append({
                "link_index": link_index,
                "source": link_item.get("source", ""),
                "target": link_item.get("target", ""),
                "missing_fields": missing_fields,
                "reason": "link 字段不存在或不是 dict",
            })
            continue

        missing_fields = []
        for field in LINK_FIELDS:
            if field in link:
                presence_counter[field] += 1
                raw_value = str(link[field])
                if field in PORT_FIELDS:
                    raw_value = strip_port_number(raw_value)
                value_counters[field][raw_value] += 1
            else:
                missing_fields.append(field)

        if missing_fields:
            missing_details.append({
                "link_index": link_index,
                "source": link_item.get("source", ""),
                "target": link_item.get("target", ""),
                "missing_fields": missing_fields,
            })

    return presence_counter, value_counters, missing_details


def write_json(path: Path, data: Any) -> None:
    """写格式化 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_presence_counters(global_ck: Counter, per_file_ck: Counter) -> None:
    """累加字段存在性计数。"""
    for field, count in per_file_ck.items():
        global_ck[field] += count


def merge_value_counters(global_ck: Dict[str, Counter], per_file_ck: Dict[str, Counter]) -> None:
    """累加字段值分布计数。"""
    for field, counter in per_file_ck.items():
        for value, count in counter.items():
            global_ck[field][value] += count


def print_bar_chart(label: str, present: int, total: int) -> str:
    """终端柱状图。"""
    pct = round(present / total * 100, 2) if total > 0 else 0.0
    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    return f"  {label:20s}  {bar}  {present}/{total} ({pct}%)"


def print_value_distribution(label: str, counter: Counter) -> None:
    """终端打印单个字段的值分布。"""
    total = sum(counter.values())
    if total == 0:
        print(f"\n--- {label}：无数据 ---")
        return
    print(f"\n--- {label}（总计 {total}）---")
    for value, count in counter.most_common():
        pct = round(count / total * 100, 2)
        bar_len = max(1, int(pct / 2))
        bar = "█" * bar_len
        display = value if value else "(空)"
        print(f"  {display:40s}  {bar}  {count} ({pct}%)")


def build_statistics(
    dataset_root: Path,
    output_dir: Path,
    splits: List[str],
    progress_interval: int,
) -> None:
    """按 split 遍历所有 JSON 文件，输出 link 字段统计。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    per_file_results: List[Dict[str, Any]] = []
    global_presence: Counter = Counter()
    global_values: Dict[str, Counter] = {field: Counter() for field in LINK_FIELDS}
    total_edges = 0
    total_files = 0
    skipped_files = 0
    issues: List[Dict[str, Any]] = []

    for split in splits:
        split_files = list_split_json_files(dataset_root, split)
        split_total = len(split_files)
        started_at = time.time()

        if progress_interval > 0:
            print(f"[{split}] start: {split_total} files", flush=True)

        for file_index, path in enumerate(split_files, start=1):
            source_file = str(path.relative_to(dataset_root))
            graph, load_detail = load_graph(path)
            if graph is None:
                skipped_files += 1
                issues.append({"split": split, "file": source_file, "error": load_detail})
                continue

            total_files += 1
            edge_count = len(graph.get("links") or [])
            total_edges += edge_count

            presence, values, missing = analyze_graph(graph)
            merge_presence_counters(global_presence, presence)
            merge_value_counters(global_values, values)

            per_file_results.append({
                "split": split,
                "source_file": source_file,
                "edge_count": edge_count,
                "field_present": {
                    field: presence.get(field, 0) for field in LINK_FIELDS
                },
                "field_missing": {
                    field: edge_count - presence.get(field, 0) for field in LINK_FIELDS
                },
                "edges_with_missing_fields": missing,
            })

            if progress_interval > 0 and (file_index % progress_interval == 0 or file_index == split_total):
                elapsed = max(0.001, time.time() - started_at)
                speed = file_index / elapsed
                remaining = max(0, split_total - file_index)
                eta = remaining / speed if speed > 0 else 0
                percent = (file_index / split_total * 100) if split_total else 100
                print(
                    f"[{split}] {file_index}/{split_total} files ({percent:.2f}%), "
                    f"elapsed {elapsed:.1f}s, {speed:.2f} files/s, eta {eta:.1f}s",
                    flush=True,
                )

    # 构建 summary
    field_summary: Dict[str, Any] = {}
    for field in LINK_FIELDS:
        present = global_presence.get(field, 0)
        counter = global_values[field]
        field_summary[field] = {
            "present": present,
            "missing": total_edges - present,
            "coverage_pct": round(present / total_edges * 100, 2) if total_edges > 0 else 0.0,
            "unique_values": len(counter),
            "value_distribution": {
                value: {
                    "count": count,
                    "percentage": round(count / present * 100, 2) if present > 0 else 0.0,
                }
                for value, count in counter.most_common()
            },
        }

    summary = {
        "dataset_root": str(dataset_root),
        "splits": splits,
        "total_files": total_files,
        "skipped_files": skipped_files,
        "total_edges": total_edges,
        "fields": field_summary,
        "issues": issues,
    }

    write_json(output_dir / "link_field_statistics.json", {
        "summary": summary,
        "per_file": per_file_results,
    })

    # 终端输出
    print(f"\n{'='*60}")
    print(f"统计完成：{total_files} 张图，{total_edges} 条边")
    print(f"{'='*60}")

    print(f"\n--- link 字段覆盖率 ---")
    for field in LINK_FIELDS:
        print(print_bar_chart(FIELD_LABELS[field], global_presence.get(field, 0), total_edges))

    for field in LINK_FIELDS:
        print_value_distribution(FIELD_LABELS[field], global_values[field])

    if skipped_files:
        print(f"\n跳过 {skipped_files} 个无法解析的文件")
    print(f"\n{'='*60}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计 links[].link 内 LEFTPORT/RIGHTPORT/CLASSNAME 的覆盖率和值分布。"
    )
    parser.add_argument(
        "dataset_root",
        nargs="?",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help=f"数据集根目录，内含 train/ 和 val/。默认：{DEFAULT_DATASET_ROOT}",
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"统计结果输出目录。默认：{DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--split",
        choices=["train", "val", "all"],
        default="all",
        help="选择统计范围：train（仅训练集）、val（仅验证集）、all（全部）。默认：all",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=DEFAULT_PROGRESS_INTERVAL,
        help="每 N 张图打印一次进度。0 表示不打印。默认：%(default)s",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.split == "all":
        splits = ["train", "val"]
    else:
        splits = [args.split]
    build_statistics(
        args.dataset_root,
        args.output_dir,
        splits,
        args.progress_interval,
    )
    print(f"统计结果已写入 {args.output_dir / 'link_field_statistics.json'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""统计 node 内关键字段的值类别分布与占比。

统计维度：
- device.TYPE         — 设备类型分类及出现比例
- device.NET_ENVIRONMENT — 网络环境分类及出现比例
- topologyNode.NODECLASS   — 节点分类及出现比例
- topologyNode.DEVICEROLE  — 设备角色及出现比例
- topologyNode.CLASSNAME   — 分类名称及出现比例
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_DATASET_ROOT = Path("datasets")
DEFAULT_OUTPUT_DIR = Path("statistics")
DEFAULT_PROGRESS_INTERVAL = 50

# 待统计的字段：路径为 (父字段, 子 key)
TARGET_FIELDS = {
    "device.TYPE": ("device", "TYPE"),
    "device.NET_ENVIRONMENT": ("device", "NET_ENVIRONMENT"),
    "topologyNode.NODECLASS": ("topologyNode", "NODECLASS"),
    "topologyNode.DEVICEROLE": ("topologyNode", "DEVICEROLE"),
    "topologyNode.CLASSNAME": ("topologyNode", "CLASSNAME"),
}

# 可读标签
FIELD_LABELS = {
    "device.TYPE": "设备类型 (TYPE)",
    "device.NET_ENVIRONMENT": "网络环境 (NET_ENVIRONMENT)",
    "topologyNode.NODECLASS": "节点分类 (NODECLASS)",
    "topologyNode.DEVICEROLE": "设备角色 (DEVICEROLE)",
    "topologyNode.CLASSNAME": "分类名称 (CLASSNAME)",
}


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


def extract_value(node: Dict[str, Any], parent_field: str, child_key: str) -> Any:
    """从 node 中提取 parent[child_key] 的值。不存在返回 None。"""
    parent = node.get(parent_field)
    if not isinstance(parent, dict):
        return None
    if child_key not in parent:
        return None
    return parent[child_key]


def analyze_graph(graph: Dict[str, Any]) -> Dict[str, Counter]:
    """分析一张图中所有 target field 的值分布。"""
    counters: Dict[str, Counter] = {name: Counter() for name in TARGET_FIELDS}

    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return counters

    for node in nodes:
        if not isinstance(node, dict):
            continue
        for field_name, (parent_field, child_key) in TARGET_FIELDS.items():
            value = extract_value(node, parent_field, child_key)
            if value is not None:
                # 统一转为字符串，保留空字符串的记录
                counters[field_name][str(value)] += 1

    return counters


def write_json(path: Path, data: Any) -> None:
    """写格式化 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_counters(global_ck: Dict[str, Counter], per_file_ck: Dict[str, Counter]) -> None:
    """将单文件的 Counter 累加到全局。"""
    for field_name, counter in per_file_ck.items():
        for value, count in counter.items():
            global_ck[field_name][value] += count


def print_distribution(label: str, counter: Counter) -> None:
    """终端打印单个字段的值分布。"""
    total = sum(counter.values())
    if total == 0:
        print(f"\n--- {label}：无数据 ---")
        return
    print(f"\n--- {label}（总计 {total}）---")
    # 按频次降序排列
    for value, count in counter.most_common():
        pct = round(count / total * 100, 2)
        bar_len = max(1, int(pct / 2))  # 每 2% 一个字符，最多 50 个字符
        bar = "█" * bar_len
        print(f"  {str(value):40s}  {bar}  {count} ({pct}%)")


def build_statistics(
    dataset_root: Path,
    output_dir: Path,
    splits: List[str],
    progress_interval: int,
) -> None:
    """按 split 遍历所有 JSON 文件，输出值分布统计。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    per_file_results: List[Dict[str, Any]] = []
    global_counters: Dict[str, Counter] = {name: Counter() for name in TARGET_FIELDS}
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
            file_counters = analyze_graph(graph)
            merge_counters(global_counters, file_counters)

            # 每文件详情
            file_detail = {"split": split, "source_file": source_file}
            for field_name in TARGET_FIELDS:
                file_detail[field_name] = dict(file_counters[field_name])
            per_file_results.append(file_detail)

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
    summary_fields: Dict[str, Any] = {}
    for field_name in TARGET_FIELDS:
        counter = global_counters[field_name]
        total = sum(counter.values())
        summary_fields[field_name] = {
            "total_count": total,
            "unique_values": len(counter),
            "distribution": {
                value: {
                    "count": count,
                    "percentage": round(count / total * 100, 2) if total > 0 else 0.0,
                }
                for value, count in counter.most_common()
            },
        }

    summary = {
        "dataset_root": str(dataset_root),
        "splits": splits,
        "total_files": total_files,
        "skipped_files": skipped_files,
        "fields": summary_fields,
        "issues": issues,
    }

    write_json(output_dir / "node_value_distribution.json", {
        "summary": summary,
        "per_file": per_file_results,
    })

    # 终端输出
    print(f"\n{'='*60}")
    print(f"统计完成：{total_files} 张图")
    print(f"{'='*60}")
    for field_name, label in FIELD_LABELS.items():
        print_distribution(label, global_counters[field_name])
    if skipped_files:
        print(f"\n跳过 {skipped_files} 个无法解析的文件")
    print(f"\n{'='*60}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计 node 内关键字段（TYPE/NET_ENVIRONMENT/NODECLASS/DEVICEROLE/CLASSNAME）的值分布。"
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
    print(f"统计结果已写入 {args.output_dir / 'node_value_distribution.json'}")


if __name__ == "__main__":
    main()

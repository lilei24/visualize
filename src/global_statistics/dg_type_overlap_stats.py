#!/usr/bin/env python3
"""统计 deviceGroups 的 DEVICEGROUPTYPES 与 nodes 的 device.TYPE 的对应关系。

统计维度：
- deviceGroups 的 DEVICEGROUPTYPES 值列表（逗号分隔的值拆分后统计）
- 每个 DEVICEGROUPTYPES 值在 nodes device.TYPE 中是否有对应
- nodes device.TYPE 中哪些值在 DEVICEGROUPTYPES 中没有出现
- 按 split 汇总
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple


DEFAULT_DATASET_ROOT = Path("datasets")
DEFAULT_OUTPUT_DIR = Path("statistics")
DEFAULT_PROGRESS_INTERVAL = 50


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


def extract_device_group_types(graph: Dict[str, Any]) -> Set[str]:
    """提取所有 deviceGroup 的 DEVICEGROUPTYPES 值，逗号分隔的会拆分。

    "AP" → {"AP"}
    "FW,LSW" → {"FW", "LSW"}
    """
    types: Set[str] = set()
    device_groups = graph.get("deviceGroups")
    if not isinstance(device_groups, list):
        return types
    for dg in device_groups:
        if not isinstance(dg, dict):
            continue
        dg_info = dg.get("deviceGroup")
        if not isinstance(dg_info, dict):
            continue
        raw = dg_info.get("DEVICEGROUPTYPES")
        if raw is None or raw == "":
            continue
        # 逗号分隔拆分，去除首尾空格
        for part in str(raw).split(","):
            part = part.strip()
            if part:
                types.add(part)
    return types


def extract_node_types(graph: Dict[str, Any]) -> Set[str]:
    """提取所有 node 的 device.TYPE 值。"""
    types: Set[str] = set()
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return types
    for node in nodes:
        if not isinstance(node, dict):
            continue
        device = node.get("device")
        if isinstance(device, dict):
            t = device.get("TYPE")
            if t is not None and t != "":
                types.add(str(t))
    return types


def analyze_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
    """分析一张图中 DEVICEGROUPTYPES 与 node TYPE 的对应关系。"""
    dg_types = extract_device_group_types(graph)
    node_types = extract_node_types(graph)

    return {
        "dg_types": dg_types,
        "node_types": node_types,
        "dg_has_node_has_not": sorted(dg_types - node_types),
        "node_has_dg_has_not": sorted(node_types - dg_types),
        "both": sorted(dg_types & node_types),
    }


def write_json(path: Path, data: Any) -> None:
    """写格式化 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_statistics(
    dataset_root: Path,
    output_dir: Path,
    splits: List[str],
    progress_interval: int,
) -> None:
    """按 split 遍历所有 JSON 文件，输出 DEVICEGROUPTYPES vs node TYPE 对应分析。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    per_file_results: List[Dict[str, Any]] = []
    global_dg_counter: Counter = Counter()          # 各 DEVICEGROUPTYPES 值出现次数
    global_node_type_counter: Counter = Counter()   # 各 node TYPE 出现次数
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
            result = analyze_graph(graph)

            # 累加全局计数：DEVICEGROUPTYPES 每图每个值只算 1 次
            for t in result["dg_types"]:
                global_dg_counter[t] += 1
            for t in result["node_types"]:
                global_node_type_counter[t] += 1

            per_file_results.append({
                "split": split,
                "source_file": source_file,
                "dg_types": sorted(result["dg_types"]),
                "node_types": sorted(result["node_types"]),
                "both": result["both"],
                "dg_only": result["dg_has_node_has_not"],
                "node_only": result["node_has_dg_has_not"],
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

    # 全局视角：统计所有图的并集
    all_dg_types = set(global_dg_counter.keys())
    all_node_types = set(global_node_type_counter.keys())
    both = sorted(all_dg_types & all_node_types)
    dg_only = sorted(all_dg_types - all_node_types)
    node_only = sorted(all_node_types - all_dg_types)

    summary = {
        "dataset_root": str(dataset_root),
        "splits": splits,
        "total_files": total_files,
        "skipped_files": skipped_files,
        "dg_type_distribution": {
            t: {
                "count": count,
                "percentage": round(count / total_files * 100, 2) if total_files > 0 else 0.0,
                "found_in_node_types": t in all_node_types,
            }
            for t, count in global_dg_counter.most_common()
        },
        "node_type_distribution": {
            t: {
                "count": count,
                "percentage": round(count / total_files * 100, 2) if total_files > 0 else 0.0,
                "found_in_dg_types": t in all_dg_types,
            }
            for t, count in global_node_type_counter.most_common()
        },
        "overlap_summary": {
            "total_dg_type_values": len(all_dg_types),
            "total_node_type_values": len(all_node_types),
            "both": both,
            "dg_only": dg_only,
            "node_only": node_only,
        },
        "issues": issues,
    }

    write_json(output_dir / "dg_vs_node_type_overlap.json", {
        "summary": summary,
        "per_file": per_file_results,
    })

    # 终端输出
    print(f"\n{'='*70}")
    print(f"统计完成：{total_files} 张图")
    print(f"{'='*70}")

    print(f"\n--- DEVICEGROUPTYPES 值分布（按出现图数）---")
    for t, count in global_dg_counter.most_common():
        pct = round(count / total_files * 100, 2) if total_files > 0 else 0.0
        bar_len = max(1, int(pct / 2))
        bar = "█" * bar_len
        mark = "✓" if t in all_node_types else "✗  (在 node TYPE 中找不到)"
        print(f"  {t:25s}  {bar}  {count:5d}张图 ({pct:5.1f}%)  {mark}")

    print(f"\n--- node TYPE 值分布（按出现图数）---")
    for t, count in global_node_type_counter.most_common():
        pct = round(count / total_files * 100, 2) if total_files > 0 else 0.0
        bar_len = max(1, int(pct / 2))
        bar = "█" * bar_len
        mark = "✓" if t in all_dg_types else "✗  (在 DEVICEGROUPTYPES 中找不到)"
        print(f"  {t:25s}  {bar}  {count:5d}张图 ({pct:5.1f}%)  {mark}")

    print(f"\n--- 重叠分析 ---")
    print(f"  DEVICEGROUPTYPES 去重值：{len(all_dg_types)} 个")
    print(f"  node TYPE 去重值：      {len(all_node_types)} 个")
    print(f"  双方共有：              {len(both)} 个  {both if both else ''}")
    if dg_only:
        print(f"  仅 DEVICEGROUPTYPES 有：{len(dg_only)} 个  {dg_only}")
    else:
        print(f"  仅 DEVICEGROUPTYPES 有：0 个")
    if node_only:
        print(f"  仅 node TYPE 有：       {len(node_only)} 个  {node_only}")
    else:
        print(f"  仅 node TYPE 有：       0 个")

    if skipped_files:
        print(f"\n跳过 {skipped_files} 个无法解析的文件")
    print(f"\n{'='*70}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计 deviceGroups.DEVICEGROUPTYPES 与 nodes.device.TYPE 的对应关系。"
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
    print(f"统计结果已写入 {args.output_dir / 'dg_vs_node_type_overlap.json'}")


if __name__ == "__main__":
    main()

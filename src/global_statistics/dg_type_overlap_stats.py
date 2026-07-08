#!/usr/bin/env python3
"""统计 deviceGroups 的 DEVICEGROUPTYPES 与 nodes 的 device.TYPE 的对应关系。

统计维度（按图统计）：
- 完全对应：DG 的值集合 == node 的值集合（图数）
- DG有 node无：DG 存在 node 中没有的值（图数）
- node有 DG无：node 存在 DG 中没有的值（图数）
- 按 split 汇总
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
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


def classify_graph(dg_types: Set[str], node_types: Set[str]) -> Dict[str, Any]:
    """对一张图的 DEVICEGROUPTYPES vs node TYPE 做三分类。

    返回字典：
    - is_match: DG == Node（完全对应）
    - dg_has_node_not: DG 有 node 没有的值
    - node_has_dg_not: node 有 DG 没有的值
    """
    dg_extra = sorted(dg_types - node_types)
    node_extra = sorted(node_types - dg_types)
    both = sorted(dg_types & node_types)

    return {
        "is_match": len(dg_extra) == 0 and len(node_extra) == 0,
        "dg_has_node_not": len(dg_extra) > 0,
        "node_has_dg_not": len(node_extra) > 0,
        "dg_extra": dg_extra,
        "node_extra": node_extra,
        "both": both,
        "dg_types": sorted(dg_types),
        "node_types": sorted(node_types),
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
    """按 split 遍历所有 JSON 文件，输出三分类统计。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    per_file_results: List[Dict[str, Any]] = []

    # 三分类计数器
    match_count = 0
    dg_has_node_not_count = 0
    node_has_dg_not_count = 0
    # 双方都没有的情况（都为空集）
    both_empty_count = 0

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
            dg_types = extract_device_group_types(graph)
            node_types = extract_node_types(graph)
            result = classify_graph(dg_types, node_types)

            if result["is_match"]:
                match_count += 1
            if result["dg_has_node_not"]:
                dg_has_node_not_count += 1
            if result["node_has_dg_not"]:
                node_has_dg_not_count += 1
            if not dg_types and not node_types:
                both_empty_count += 1

            per_file_results.append({
                "split": split,
                "source_file": source_file,
                **result,
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

    summary = {
        "dataset_root": str(dataset_root),
        "splits": splits,
        "total_files": total_files,
        "skipped_files": skipped_files,
        "three_way_classification": {
            "完全对应 (DG == Node)": {
                "count": match_count,
                "percentage": round(match_count / total_files * 100, 2) if total_files > 0 else 0.0,
            },
            "DG有 Node无 (DG not subset of Node)": {
                "count": dg_has_node_not_count,
                "percentage": round(dg_has_node_not_count / total_files * 100, 2) if total_files > 0 else 0.0,
            },
            "Node有 DG无 (Node not subset of DG)": {
                "count": node_has_dg_not_count,
                "percentage": round(node_has_dg_not_count / total_files * 100, 2) if total_files > 0 else 0.0,
            },
        },
        "note": "后两类可能重叠（一张图可同时属于后两类）",
        "both_empty": both_empty_count,
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

    def bar(pct: float) -> str:
        return "█" * max(1, int(pct / 2)) + "░" * max(0, 50 - int(pct / 2))

    print(f"\n  1. 完全对应 (DG == Node)：           {match_count:5d}张图  ({round(match_count/total_files*100,1) if total_files>0 else 0}%)")
    print(f"     {bar(round(match_count/total_files*100,1) if total_files>0 else 0)}")
    print(f"\n  2. DG有 Node无 (DG not subset of Node)：{dg_has_node_not_count:5d}张图  ({round(dg_has_node_not_count/total_files*100,1) if total_files>0 else 0}%)")
    print(f"     {bar(round(dg_has_node_not_count/total_files*100,1) if total_files>0 else 0)}")
    print(f"\n  3. Node有 DG无 (Node not subset of DG)：{node_has_dg_not_count:5d}张图  ({round(node_has_dg_not_count/total_files*100,1) if total_files>0 else 0}%)")
    print(f"     {bar(round(node_has_dg_not_count/total_files*100,1) if total_files>0 else 0)}")

    if both_empty_count:
        print(f"\n  注：{both_empty_count} 张图双方均为空集（归入完全对应）")

    if skipped_files:
        print(f"\n跳过 {skipped_files} 个无法解析的文件")
    print(f"\n{'='*70}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按图统计 DEVICEGROUPTYPES vs node TYPE 的三分类（完全对应/DG有node无/node有DG无）。"
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

#!/usr/bin/env python3
"""通过 links 统计边两端节点的 device.TYPE 配对关系。

统计维度：
- 每条边的 source node 和 target node 的 device.TYPE 作为一对进行统计
- 统计每种 TYPE 配对的边数量和占比
- 按 split 汇总
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


def build_node_type_map(nodes: Any) -> Dict[str, str]:
    """构建 node_id -> device.TYPE 的映射。"""
    type_map: Dict[str, str] = {}
    if not isinstance(nodes, list):
        return type_map
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        if node_id is None:
            continue
        device = node.get("device")
        if isinstance(device, dict):
            device_type = device.get("TYPE", "")
        else:
            device_type = ""
        type_map[str(node_id)] = str(device_type)
    return type_map


def analyze_graph_edges(graph: Dict[str, Any]) -> Counter:
    """分析一张图中所有边的 TYPE 配对。"""
    pair_counter: Counter = Counter()

    node_type_map = build_node_type_map(graph.get("nodes"))

    links = graph.get("links")
    if not isinstance(links, list):
        return pair_counter

    for link in links:
        if not isinstance(link, dict):
            continue
        source_id = str(link.get("source", ""))
        target_id = str(link.get("target", ""))
        if not source_id or not target_id:
            continue

        source_type = node_type_map.get(source_id, "<unknown>")
        target_type = node_type_map.get(target_id, "<unknown>")

        # 无向图：按字典序排序，避免 A-B 和 B-A 被算成两类
        if source_type <= target_type:
            pair = (source_type, target_type)
        else:
            pair = (target_type, source_type)

        pair_counter[pair] += 1

    return pair_counter


def write_json(path: Path, data: Any) -> None:
    """写格式化 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_distribution(label: str, counter: Counter) -> None:
    """终端打印边 TYPE 配对分布。"""
    total = sum(counter.values())
    if total == 0:
        print(f"\n{label}：无数据")
        return
    print(f"\n{label}（总计 {total} 条边）：")
    for (type_a, type_b), count in counter.most_common():
        pct = round(count / total * 100, 2)
        bar_len = max(1, int(pct / 2))
        bar = "█" * bar_len
        pair_str = f"{type_a}  <->  {type_b}"
        print(f"  {pair_str:50s}  {bar}  {count} ({pct}%)")


def build_statistics(
    dataset_root: Path,
    output_dir: Path,
    splits: List[str],
    progress_interval: int,
) -> None:
    """按 split 遍历所有 JSON 文件，输出边 TYPE 配对统计。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    per_file_results: List[Dict[str, Any]] = []
    global_pair_counter: Counter = Counter()
    total_edges = 0
    total_files = 0
    skipped_files = 0
    files_without_links = 0
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

            if edge_count == 0:
                files_without_links += 1

            file_pairs = analyze_graph_edges(graph)
            for pair, count in file_pairs.items():
                global_pair_counter[pair] += count

            per_file_results.append({
                "split": split,
                "source_file": source_file,
                "edge_count": edge_count,
                "type_pairs": {f"{a} <-> {b}": c for (a, b), c in file_pairs.most_common()},
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

    # summary
    summary = {
        "dataset_root": str(dataset_root),
        "splits": splits,
        "total_files": total_files,
        "skipped_files": skipped_files,
        "files_without_links": files_without_links,
        "total_edges": total_edges,
        "unique_type_pairs": len(global_pair_counter),
        "type_pair_distribution": {
            f"{a} <-> {b}": {
                "count": count,
                "percentage": round(count / total_edges * 100, 2) if total_edges > 0 else 0.0,
            }
            for (a, b), count in global_pair_counter.most_common()
        },
        "issues": issues,
    }

    write_json(output_dir / "edge_type_pair_statistics.json", {
        "summary": summary,
        "per_file": per_file_results,
    })

    # 终端输出
    print(f"\n{'='*60}")
    print(f"统计完成：{total_files} 张图，{total_edges} 条边，{len(global_pair_counter)} 种 TYPE 配对")
    if files_without_links:
        print(f"其中 {files_without_links} 张图没有 links")
    print(f"{'='*60}")
    print_distribution("边连接 TYPE 配对分布", global_pair_counter)
    if skipped_files:
        print(f"\n跳过 {skipped_files} 个无法解析的文件")
    print(f"\n{'='*60}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="通过 links 统计边两端节点的 device.TYPE 配对关系。"
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
    print(f"统计结果已写入 {args.output_dir / 'edge_type_pair_statistics.json'}")


if __name__ == "__main__":
    main()

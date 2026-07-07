#!/usr/bin/env python3
"""统计网络图 JSON 中 nodes 数量及每个 node 内关键字段的存在性。

统计维度：
- 每张图的 nodes 总数
- 每个 node 的 id / device / topologyNode / configs 字段是否存在
- 按 split 汇总整体覆盖率和缺失情况。
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_DATASET_ROOT = Path("datasets")
DEFAULT_OUTPUT_DIR = Path("statistics")
DEFAULT_PROGRESS_INTERVAL = 50

# 待检查字段列表
NODE_FIELDS = ["id", "device", "topologyNode", "configs"]


@dataclass
class NodeFieldPresence:
    """单个 node 内各字段是否存在。"""

    has_id: bool = False
    has_device: bool = False
    has_topologyNode: bool = False
    has_configs: bool = False

    @classmethod
    def from_node(cls, node: Dict[str, Any]) -> "NodeFieldPresence":
        return cls(
            has_id="id" in node,
            has_device="device" in node,
            has_topologyNode="topologyNode" in node,
            has_configs="configs" in node,
        )

    def missing_fields(self) -> List[str]:
        missing = []
        if not self.has_id:
            missing.append("id")
        if not self.has_device:
            missing.append("device")
        if not self.has_topologyNode:
            missing.append("topologyNode")
        if not self.has_configs:
            missing.append("configs")
        return missing


@dataclass
class FileStats:
    """单张图的统计。"""

    source_file: str = ""
    node_count: int = 0
    field_counts: Counter = field(default_factory=Counter)
    missing_nodes: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def id_present(self) -> int:
        return self.field_counts.get("id", 0)

    @property
    def device_present(self) -> int:
        return self.field_counts.get("device", 0)

    @property
    def topologyNode_present(self) -> int:
        return self.field_counts.get("topologyNode", 0)

    @property
    def configs_present(self) -> int:
        return self.field_counts.get("configs", 0)


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


def load_graph(path: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    """读取一张图。返回 (graph, "") 成功，(None, detail) 失败。"""
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)
    if not isinstance(graph, dict):
        return None, f"top-level JSON type is {type(graph).__name__}, expected object"
    return graph, ""


def analyze_graph(graph: Dict[str, Any], source_file: str) -> FileStats:
    """分析单张图的 node 字段统计。"""
    stats = FileStats(source_file=source_file)
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return stats

    stats.node_count = len(nodes)
    for node_index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        presence = NodeFieldPresence.from_node(node)
        for field in NODE_FIELDS:
            if getattr(presence, f"has_{field}"):
                stats.field_counts[field] += 1
        missing = presence.missing_fields()
        if missing:
            stats.missing_nodes.append({
                "node_index": node_index,
                "node_id": node.get("id", None),
                "missing_fields": missing,
            })

    return stats


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
    """按 split 遍历所有 JSON 文件，输出统计结果。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    per_file_results: List[Dict[str, Any]] = []
    global_field_counts: Counter = Counter()
    total_nodes = 0
    total_files = 0
    skipped_files = 0
    issues: List[Dict[str, Any]] = []

    for split_index, split in enumerate(splits):
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

            file_stats = analyze_graph(graph, source_file)
            total_nodes += file_stats.node_count
            total_files += 1
            for field in NODE_FIELDS:
                global_field_counts[field] += getattr(file_stats, f"{field}_present")

            per_file_results.append({
                "split": split,
                "source_file": source_file,
                "node_count": file_stats.node_count,
                "field_present": {
                    "id": file_stats.id_present,
                    "device": file_stats.device_present,
                    "topologyNode": file_stats.topologyNode_present,
                    "configs": file_stats.configs_present,
                },
                "field_missing": {
                    "id": file_stats.node_count - file_stats.id_present,
                    "device": file_stats.node_count - file_stats.device_present,
                    "topologyNode": file_stats.node_count - file_stats.topologyNode_present,
                    "configs": file_stats.node_count - file_stats.configs_present,
                },
                "nodes_with_missing_fields": file_stats.missing_nodes,
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

    # 汇总
    summary = {
        "dataset_root": str(dataset_root),
        "splits": splits,
        "total_files": total_files,
        "skipped_files": skipped_files,
        "total_nodes": total_nodes,
        "global_field_present": {
            "id": global_field_counts["id"],
            "device": global_field_counts["device"],
            "topologyNode": global_field_counts["topologyNode"],
            "configs": global_field_counts["configs"],
        },
        "global_field_coverage": {
            field: (
                round(global_field_counts[field] / total_nodes * 100, 2)
                if total_nodes > 0
                else 0.0
            )
            for field in NODE_FIELDS
        },
        "issues": issues,
    }

    write_json(output_dir / "node_field_statistics.json", {
        "summary": summary,
        "per_file": per_file_results,
    })

    # 终端输出摘要
    print(f"\n{'='*60}")
    print(f"统计完成：{total_files} 张图，{total_nodes} 个节点")
    print(f"{'='*60}")
    print(f"字段覆盖率：")
    for field in NODE_FIELDS:
        present = global_field_counts[field]
        pct = round(present / total_nodes * 100, 2) if total_nodes > 0 else 0.0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {field:15s}  {bar}  {present}/{total_nodes} ({pct}%)")
    if skipped_files:
        print(f"\n跳过 {skipped_files} 个无法解析的文件")
    if issues:
        print(f"详见 {output_dir / 'node_field_statistics.json'}")
    print(f"{'='*60}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计网络图 JSON 中 nodes 数量及关键字段存在性。"
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
    # 将 --split 选择转为 splits 列表
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
    print(f"统计结果已写入 {args.output_dir / 'node_field_statistics.json'}")


if __name__ == "__main__":
    main()

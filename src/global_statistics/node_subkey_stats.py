#!/usr/bin/env python3
"""统计 node 内 device / topologyNode / configs 的顶层 key 分布与覆盖率。

统计维度：
- device 内各顶层 key（NAME/MANUFACTURER/MODEL/TYPE 等）的出现次数和覆盖率
- topologyNode 内各顶层 key（NODECLASS/DEVICEROLE/CLASSNAME 等）的出现次数和覆盖率
- configs[] 内各配置类型 key（cloud-ap-interfaces/ap-psk 等）的出现次数和覆盖率
- 按 split 汇总。

与 node_field_stats.py 的区别：前者统计 node 顶层是否包含 device/topologyNode/configs，
本脚本进一步深入到这些字段内部的 key 级别。
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


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


def load_graph(path: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    """读取一张图。返回 (graph, "") 成功，(None, detail) 失败。"""
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)
    if not isinstance(graph, dict):
        return None, f"top-level JSON type is {type(graph).__name__}, expected object"
    return graph, ""


def extract_device_keys(device: Any) -> List[str]:
    """提取 device dict 内的顶层 key 列表。"""
    if not isinstance(device, dict):
        return []
    return sorted(device.keys())


def extract_topology_node_keys(topology_node: Any) -> List[str]:
    """提取 topologyNode dict 内的顶层 key 列表。"""
    if not isinstance(topology_node, dict):
        return []
    return sorted(topology_node.keys())


def extract_configs_keys(configs: Any) -> List[str]:
    """提取 configs 列表中每个配置对象的顶层 key。

    configs 是 [{"key1": {...}}, {"key2": {...}}, ...]，返回所有这些 key 名。
    """
    keys: List[str] = []
    if not isinstance(configs, list):
        return keys
    for config_item in configs:
        if isinstance(config_item, dict):
            keys.extend(sorted(config_item.keys()))
    return keys


def analyze_node_subkeys(graph: Dict[str, Any]) -> Dict[str, Any]:
    """分析一张图中所有 node 的子 key 分布。

    返回包含三个 Counter 的字典：
    - device_keys: {key_name: count}
    - topology_node_keys: {key_name: count}
    - configs_keys: {key_name: count}
    以及各字段所在的总 node 数（分母）。
    """
    device_key_counts: Counter = Counter()
    topology_node_key_counts: Counter = Counter()
    configs_key_counts: Counter = Counter()
    nodes_with_device = 0
    nodes_with_topology_node = 0
    nodes_with_configs = 0

    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return {
            "device_keys": dict(device_key_counts),
            "topology_node_keys": dict(topology_node_key_counts),
            "configs_keys": dict(configs_key_counts),
            "nodes_with_device": nodes_with_device,
            "nodes_with_topology_node": nodes_with_topology_node,
            "nodes_with_configs": nodes_with_configs,
        }

    for node in nodes:
        if not isinstance(node, dict):
            continue

        device = node.get("device")
        if isinstance(device, dict):
            nodes_with_device += 1
            for key in extract_device_keys(device):
                device_key_counts[key] += 1

        topology_node = node.get("topologyNode")
        if isinstance(topology_node, dict):
            nodes_with_topology_node += 1
            for key in extract_topology_node_keys(topology_node):
                topology_node_key_counts[key] += 1

        configs = node.get("configs")
        if isinstance(configs, list):
            nodes_with_configs += 1
            for key in extract_configs_keys(configs):
                configs_key_counts[key] += 1

    return {
        "device_keys": dict(device_key_counts),
        "topology_node_keys": dict(topology_node_key_counts),
        "configs_keys": dict(configs_key_counts),
        "nodes_with_device": nodes_with_device,
        "nodes_with_topology_node": nodes_with_topology_node,
        "nodes_with_configs": nodes_with_configs,
    }


def write_json(path: Path, data: Any) -> None:
    """写格式化 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_subkey_counters(global_ck: Dict[str, Counter], per_file_ck: Dict[str, Any]) -> None:
    """将单文件的子 key 计数累加到全局 Counter 中。"""
    for category in ("device_keys", "topology_node_keys", "configs_keys"):
        for key, count in per_file_ck[category].items():
            global_ck[category][key] += count


def print_bar_chart(label: str, present: int, total: int) -> str:
    """终端柱状图。"""
    pct = round(present / total * 100, 2) if total > 0 else 0.0
    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    return f"  {label:30s}  {bar}  {present}/{total} ({pct}%)"


def build_statistics(
    dataset_root: Path,
    output_dir: Path,
    splits: List[str],
    progress_interval: int,
) -> None:
    """按 split 遍历所有 JSON 文件，输出子 key 统计结果。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    per_file_results: List[Dict[str, Any]] = []
    global_counts: Dict[str, Counter] = defaultdict(Counter)
    total_nodes = 0
    total_nodes_with_device = 0
    total_nodes_with_topology_node = 0
    total_nodes_with_configs = 0
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

            result = analyze_node_subkeys(graph)

            node_count = len(graph.get("nodes") or [])
            total_nodes += node_count
            total_nodes_with_device += result["nodes_with_device"]
            total_nodes_with_topology_node += result["nodes_with_topology_node"]
            total_nodes_with_configs += result["nodes_with_configs"]
            total_files += 1

            merge_subkey_counters(global_counts, result)

            per_file_results.append({
                "split": split,
                "source_file": source_file,
                "node_count": node_count,
                "nodes_with_device": result["nodes_with_device"],
                "nodes_with_topology_node": result["nodes_with_topology_node"],
                "nodes_with_configs": result["nodes_with_configs"],
                "device_keys": result["device_keys"],
                "topology_node_keys": result["topology_node_keys"],
                "configs_keys": result["configs_keys"],
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

    # 将 Counter 按频次降序排列
    sorted_device_keys = sorted(global_counts["device_keys"].items(), key=lambda x: -x[1])
    sorted_topology_node_keys = sorted(global_counts["topology_node_keys"].items(), key=lambda x: -x[1])
    sorted_configs_keys = sorted(global_counts["configs_keys"].items(), key=lambda x: -x[1])

    summary = {
        "dataset_root": str(dataset_root),
        "splits": splits,
        "total_files": total_files,
        "skipped_files": skipped_files,
        "total_nodes": total_nodes,
        "total_nodes_with_device": total_nodes_with_device,
        "total_nodes_with_topology_node": total_nodes_with_topology_node,
        "total_nodes_with_configs": total_nodes_with_configs,
        "device_keys": {
            "total_nodes_with_device": total_nodes_with_device,
            "keys": {key: count for key, count in sorted_device_keys},
            "coverage": {
                key: {
                    "count": count,
                    "coverage_pct": (
                        round(count / total_nodes_with_device * 100, 2)
                        if total_nodes_with_device > 0 else 0.0
                    ),
                }
                for key, count in sorted_device_keys
            },
        },
        "topology_node_keys": {
            "total_nodes_with_topology_node": total_nodes_with_topology_node,
            "keys": {key: count for key, count in sorted_topology_node_keys},
            "coverage": {
                key: {
                    "count": count,
                    "coverage_pct": (
                        round(count / total_nodes_with_topology_node * 100, 2)
                        if total_nodes_with_topology_node > 0 else 0.0
                    ),
                }
                for key, count in sorted_topology_node_keys
            },
        },
        "configs_keys": {
            "total_nodes_with_configs": total_nodes_with_configs,
            "keys": {key: count for key, count in sorted_configs_keys},
            "coverage": {
                key: {
                    "count": count,
                    "coverage_pct": (
                        round(count / total_nodes_with_configs * 100, 2)
                        if total_nodes_with_configs > 0 else 0.0
                    ),
                }
                for key, count in sorted_configs_keys
            },
        },
        "issues": issues,
    }

    write_json(output_dir / "node_subkey_statistics.json", {
        "summary": summary,
        "per_file": per_file_results,
    })

    # 终端输出摘要
    print(f"\n{'='*60}")
    print(f"统计完成：{total_files} 张图，{total_nodes} 个节点")
    print(f"{'='*60}")

    # device keys
    print(f"\n--- device  顶层 key 覆盖率（节点数={total_nodes_with_device}）---")
    if sorted_device_keys:
        for key, count in sorted_device_keys:
            print(print_bar_chart(key, count, total_nodes_with_device))
    else:
        print("  (无)")

    # topologyNode keys
    print(f"\n--- topologyNode 顶层 key 覆盖率（节点数={total_nodes_with_topology_node}）---")
    if sorted_topology_node_keys:
        for key, count in sorted_topology_node_keys:
            print(print_bar_chart(key, count, total_nodes_with_topology_node))
    else:
        print("  (无)")

    # configs keys
    print(f"\n--- configs 配置类型 key 覆盖率（节点数={total_nodes_with_configs}）---")
    if sorted_configs_keys:
        for key, count in sorted_configs_keys:
            print(print_bar_chart(key, count, total_nodes_with_configs))
    else:
        print("  (无)")

    if skipped_files:
        print(f"\n跳过 {skipped_files} 个无法解析的文件")
    print(f"{'='*60}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计 node 内 device/topologyNode/configs 的顶层 key 分布与覆盖率。"
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
    print(f"统计结果已写入 {args.output_dir / 'node_subkey_statistics.json'}")


if __name__ == "__main__":
    main()

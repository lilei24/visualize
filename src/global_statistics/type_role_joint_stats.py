#!/usr/bin/env python3
"""统计 device.TYPE 与 topologyNode.DEVICEROLE 的联合分布。

统计维度：
- 每个 node 的 (device.TYPE, topologyNode.DEVICEROLE) 组合的出现次数
- 按 TYPE 行、DEVICEROLE 列展示交叉表
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


def extract_joint_values(node: Dict[str, Any]) -> Tuple[str, str] | None:
    """从 node 中提取 (device.TYPE, topologyNode.DEVICEROLE) 组合。"""
    device = node.get("device")
    device_type = ""
    if isinstance(device, dict):
        device_type = str(device.get("TYPE", ""))

    topology_node = node.get("topologyNode")
    device_role = ""
    if isinstance(topology_node, dict):
        device_role = str(topology_node.get("DEVICEROLE", ""))

    return (device_type, device_role)


def analyze_graph(graph: Dict[str, Any]) -> Counter:
    """分析一张图中 (TYPE, DEVICEROLE) 联合分布。"""
    pair_counter: Counter = Counter()

    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return pair_counter

    for node in nodes:
        if not isinstance(node, dict):
            continue
        pair = extract_joint_values(node)
        pair_counter[pair] += 1

    return pair_counter


def write_json(path: Path, data: Any) -> None:
    """写格式化 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_counters(global_ck: Counter, per_file_ck: Counter) -> None:
    """将单文件的 Counter 累加到全局。"""
    for pair, count in per_file_ck.items():
        global_ck[pair] += count


def print_joint_distribution(counter: Counter, total: int) -> None:
    """终端打印联合分布：按 TYPE 分组展示各 DEVICEROLE。"""
    if total == 0:
        print("无数据")
        return

    # 收集行(TYPE)和列(DEVICEROLE)
    types: Dict[str, Counter] = defaultdict(Counter)
    all_roles: set = set()
    for (device_type, device_role), count in counter.items():
        types[device_type][device_role] += count
        all_roles.add(device_role)

    sorted_types = sorted(types.items(), key=lambda x: -sum(x[1].values()))
    sorted_roles = sorted(all_roles, key=lambda r: -sum(c[r] for c in types.values()))

    # 按 TYPE 分组输出
    print(f"\n--- device.TYPE × topologyNode.DEVICEROLE 联合分布（总计 {total} 个节点）---")
    for device_type, role_counter in sorted_types:
        type_total = sum(role_counter.values())
        pct = round(type_total / total * 100, 2) if total > 0 else 0.0
        parts = [f"{role}={role_counter.get(role, 0)}" for role in sorted_roles]
        print(f"  TYPE={device_type:30s}  ({type_total:5d}, {pct:5.1f}%)  |  {'  '.join(parts)}")

    # 按 DEVICEROLE 分组汇总
    print(f"\n--- 各 DEVICEROLE 的 TYPE 分布 ---")
    for role in sorted_roles:
        role_total = sum(c.get(role, 0) for c in types.values())
        pct = round(role_total / total * 100, 2) if total > 0 else 0.0
        print(f"  DEVICEROLE={role:30s}  节点数={role_total:5d} ({pct}%)")
        for dtype, rc in sorted_types:
            if rc.get(role, 0) > 0:
                print(f"    ├─ TYPE={dtype:25s}  {rc.get(role, 0)}")


def build_statistics(
    dataset_root: Path,
    output_dir: Path,
    splits: List[str],
    progress_interval: int,
) -> None:
    """按 split 遍历所有 JSON 文件，输出联合分布统计。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    per_file_results: List[Dict[str, Any]] = []
    global_pair_counter: Counter = Counter()
    total_nodes_with_both = 0
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
            file_pairs = analyze_graph(graph)
            total_nodes_with_both += sum(file_pairs.values())
            merge_counters(global_pair_counter, file_pairs)

            per_file_results.append({
                "split": split,
                "source_file": source_file,
                "type_role_pairs": {
                    f"TYPE={t}, DEVICEROLE={r}": c
                    for (t, r), c in file_pairs.most_common()
                },
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

    # 收集行列信息
    types: Dict[str, Counter] = defaultdict(Counter)
    all_roles: set = set()
    for (device_type, device_role), count in global_pair_counter.items():
        types[device_type][device_role] += count
        all_roles.add(device_role)

    sorted_types = sorted(types.items(), key=lambda x: -sum(x[1].values()))
    sorted_roles = sorted(all_roles, key=lambda r: -sum(c[r] for c in types.values()))

    # 构建联合分布矩阵
    joint_distribution: Dict[str, Any] = {}
    for device_type, role_counter in sorted_types:
        type_total = sum(role_counter.values())
        joint_distribution[device_type] = {
            "total": type_total,
            "percentage": round(type_total / total_nodes_with_both * 100, 2) if total_nodes_with_both > 0 else 0.0,
            "by_role": {
                role: {
                    "count": role_counter.get(role, 0),
                    "percentage": (
                        round(role_counter.get(role, 0) / type_total * 100, 2)
                        if type_total > 0 else 0.0
                    ),
                }
                for role in sorted_roles
            },
        }

    # 各 DEVICEROLE 汇总
    role_summary: Dict[str, Any] = {}
    for role in sorted_roles:
        role_total = sum(c.get(role, 0) for c in types.values())
        role_summary[role] = {
            "total": role_total,
            "percentage": round(role_total / total_nodes_with_both * 100, 2) if total_nodes_with_both > 0 else 0.0,
            "by_type": {
                dtype: tc.get(role, 0)
                for dtype, tc in sorted_types
                if tc.get(role, 0) > 0
            },
        }

    summary = {
        "dataset_root": str(dataset_root),
        "splits": splits,
        "total_files": total_files,
        "skipped_files": skipped_files,
        "total_nodes_with_both_fields": total_nodes_with_both,
        "unique_types": len(types),
        "unique_roles": len(all_roles),
        "type_distribution": joint_distribution,
        "role_summary": role_summary,
        "issues": issues,
    }

    write_json(output_dir / "type_role_joint_distribution.json", {
        "summary": summary,
        "per_file": per_file_results,
    })

    # 终端输出
    print(f"\n{'='*60}")
    print(f"统计完成：{total_files} 张图，{total_nodes_with_both} 个节点有 TYPE+DEVICEROLE")
    print(f"{len(types)} 种 TYPE × {len(all_roles)} 种 DEVICEROLE")
    print(f"{'='*60}")
    print_joint_distribution(global_pair_counter, total_nodes_with_both)
    if skipped_files:
        print(f"\n跳过 {skipped_files} 个无法解析的文件")
    print(f"\n{'='*60}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计 device.TYPE 与 topologyNode.DEVICEROLE 的联合分布。"
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
    print(f"统计结果已写入 {args.output_dir / 'type_role_joint_distribution.json'}")


if __name__ == "__main__":
    main()

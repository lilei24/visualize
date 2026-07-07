#!/usr/bin/env python3
"""按 device.TYPE 统计每种设备类型下 configs 的配置类型分布。

统计维度：
- 将 nodes 按 device.TYPE 分组
- 统计每种 TYPE 下 configs[] 中各配置 key 的出现次数和占比
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


def analyze_graph_configs_by_type(graph: Dict[str, Any]) -> Dict[str, Counter]:
    """按 device.TYPE 分组统计 configs 配置 key 分布。

    返回 {device_type: Counter(config_key: count)}
    """
    result: Dict[str, Counter] = defaultdict(Counter)

    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return result

    for node in nodes:
        if not isinstance(node, dict):
            continue

        # 获取 device.TYPE
        device = node.get("device")
        device_type = ""
        if isinstance(device, dict):
            device_type = str(device.get("TYPE", ""))

        # 获取 configs 的 key
        configs = node.get("configs")
        if not isinstance(configs, list):
            continue

        for config_item in configs:
            if isinstance(config_item, dict):
                for config_key in config_item:
                    result[device_type][config_key] += 1

    return result


def write_json(path: Path, data: Any) -> None:
    """写格式化 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_counters(global_ck: Dict[str, Counter], per_file_ck: Dict[str, Counter]) -> None:
    """将单文件的 Counter 按 device_type 累加到全局。"""
    for device_type, config_counter in per_file_ck.items():
        for config_key, count in config_counter.items():
            global_ck[device_type][config_key] += count


def print_distribution(device_type: str, counter: Counter, global_total: int) -> None:
    """终端打印单个 device.TYPE 的 configs 分布。"""
    total = sum(counter.values())
    bar_total = max(total, global_total)
    print(f"\n--- device.TYPE = \"{device_type}\"（配置项总数 {total}，占全局 {round(total/global_total*100,2) if global_total > 0 else 0}%）---")
    for config_key, count in counter.most_common():
        pct = round(count / total * 100, 2) if total > 0 else 0.0
        bar_len = max(1, int(pct / 2))
        bar = "█" * bar_len
        print(f"  {config_key:40s}  {bar}  {count} ({pct}%)")


def build_statistics(
    dataset_root: Path,
    output_dir: Path,
    splits: List[str],
    progress_interval: int,
) -> None:
    """按 split 遍历所有 JSON 文件，输出 TYPE-configs 分布统计。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    per_file_results: List[Dict[str, Any]] = []
    global_counters: Dict[str, Counter] = defaultdict(Counter)
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
            file_counters = analyze_graph_configs_by_type(graph)
            merge_counters(global_counters, file_counters)

            # 每文件详情
            file_detail: Dict[str, Any] = {"split": split, "source_file": source_file}
            for device_type, config_counter in file_counters.items():
                file_detail[device_type or "<empty>"] = dict(config_counter)
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

    # 构建 summary：按每种 TYPE 的配置总数降序排列
    global_total = sum(sum(c.values()) for c in global_counters.values())
    sorted_types = sorted(global_counters.items(), key=lambda x: -sum(x[1].values()))

    summary_types: Dict[str, Any] = {}
    for device_type, config_counter in sorted_types:
        type_total = sum(config_counter.values())
        summary_types[device_type] = {
            "total_config_items": type_total,
            "unique_config_keys": len(config_counter),
            "percentage_of_global": (
                round(type_total / global_total * 100, 2) if global_total > 0 else 0.0
            ),
            "config_key_distribution": {
                config_key: {
                    "count": count,
                    "percentage": round(count / type_total * 100, 2) if type_total > 0 else 0.0,
                }
                for config_key, count in config_counter.most_common()
            },
        }

    summary = {
        "dataset_root": str(dataset_root),
        "splits": splits,
        "total_files": total_files,
        "skipped_files": skipped_files,
        "global_total_config_items": global_total,
        "device_types": summary_types,
        "issues": issues,
    }

    write_json(output_dir / "type_configs_distribution.json", {
        "summary": summary,
        "per_file": per_file_results,
    })

    # 终端输出
    print(f"\n{'='*60}")
    print(f"统计完成：{total_files} 张图，{len(global_counters)} 种 device.TYPE")
    print(f"全局配置项总数：{global_total}")
    print(f"{'='*60}")
    for device_type, config_counter in sorted_types:
        print_distribution(device_type, config_counter, global_total)
    if skipped_files:
        print(f"\n跳过 {skipped_files} 个无法解析的文件")
    print(f"\n{'='*60}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按 device.TYPE 统计每种设备类型下 configs 的配置类型分布。"
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
    print(f"统计结果已写入 {args.output_dir / 'type_configs_distribution.json'}")


if __name__ == "__main__":
    main()

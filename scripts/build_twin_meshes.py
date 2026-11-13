"""把 reBot B601-DM 的公开网格压缩成数字孪生用的轻量外形文件。

输入：建模资料包 zip（内含 rebot-joycon 的 URDF/reBot_B601_DM/meshes/colored_*.stl）。
输出：rearm/ui/static/modules/twin/meshes/b601.json（清单）和 b601.bin（顶点 + 索引）。

做法是顶点聚类：把空间切成边长 cell 的小格，同一格里的顶点并成一个，退化的三角形丢掉。
只改外观细节，不改连杆坐标系；运动学仍然只看 arm-config.js。

    .venv/bin/python scripts/build_twin_meshes.py <资料包.zip> [--cell-mm 2.5]
"""
import argparse
import json
import os
import re
import zipfile
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "rearm/ui/static/modules/twin/meshes"
# 网格文件名前缀 → 孪生里的坐标系（kinematics.forward 的键；base 为固定底座，tool 为末端）
LINKS = {"base_link": "base", "link1": "joint1", "link2": "joint2", "link3": "joint3", "link4": "joint4",
         "link5": "joint5", "link6": "joint6", "gripper_base": "tool", "left_finger": "tool", "right_finger": "tool"}
STL = np.dtype([("normal", "<3f4"), ("vertices", "<9f4"), ("attr", "<u2")])


def decimate(vertices: np.ndarray, cell: float) -> tuple[np.ndarray, np.ndarray]:
    """vertices: (n, 3, 3) triangles in metres → (points, triangle indices) after vertex clustering."""
    flat = vertices.reshape(-1, 3)
    keys = np.floor(flat / cell).astype(np.int64)
    _, inverse, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    inverse = inverse.reshape(-1)
    points = np.zeros((len(counts), 3))
    np.add.at(points, inverse, flat)
    points /= counts[:, None]                      # 每格取平均位置
    tris = inverse.reshape(-1, 3)
    keep = (tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])
    tris = tris[keep]
    tris = tris[np.unique(np.sort(tris, axis=1), axis=0, return_index=True)[1]]  # 去重复面
    used, remap = np.unique(tris, return_inverse=True)
    return points[used].astype("<f4"), remap.reshape(-1, 3).astype("<u4")


def main(archive: str, cell_mm: float):
    parts, blobs, offset, before, after = [], [], 0, 0, 0
    with zipfile.ZipFile(archive) as z:
        names = sorted(n for n in z.namelist() if re.search(r"/meshes/colored_[^/]+\.stl$", n))
        if not names:
            raise SystemExit("资料包里没有 meshes/colored_*.stl")
        for name in names:
            stem = os.path.basename(name)[len("colored_"):-len(".stl")]
            link = next((key for key in sorted(LINKS, key=len, reverse=True) if stem.startswith(key + "_")), None)
            if link is None:
                continue
            material = stem[len(link) + 1:]
            data = z.read(name)
            count = int.from_bytes(data[80:84], "little")
            triangles = np.frombuffer(data, dtype=STL, count=count, offset=84)["vertices"].reshape(-1, 3, 3).astype(float)
            points, indices = decimate(triangles, cell_mm / 1000)
            before += count
            after += len(indices)
            part = {"frame": LINKS[link], "source": stem, "material": material,
                    "side": "left" if link == "left_finger" else "right" if link == "right_finger" else None}
            for key, array in (("positions", points), ("indices", indices)):
                blob = array.tobytes()
                part[key] = {"offset": offset, "count": int(array.size)}
                blobs.append(blob)
                offset += len(blob)
            parts.append(part)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "b601.bin").write_bytes(b"".join(blobs))
    manifest = {"model": "reBot Arm B601-DM", "units": "m", "cell_mm": cell_mm, "triangles": after,
                "source": "box2ai-robotics/rebot-joycon @ dd97975, URDF/reBot_B601_DM/meshes/colored_*.stl（Seeed 原始设计，CERN-OHL-W-2.0）",
                "parts": parts}
    (OUT / "b601.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(parts)} parts, {before} → {after} triangles, {offset / 1e6:.2f} MB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("archive")
    parser.add_argument("--cell-mm", type=float, default=2.5)
    args = parser.parse_args()
    main(args.archive, args.cell_mm)

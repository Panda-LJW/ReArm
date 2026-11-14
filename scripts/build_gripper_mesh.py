"""将自制单根夹指 STEP 三角化，安装为 end_link 系中零开口的左右夹指。

转换环境（仅临时目录，不改项目 .venv）：
    python3 -m venv "$TMPDIR/rearm-gripper-venv"
    "$TMPDIR/rearm-gripper-venv/bin/pip" install gmsh numpy
运行（gmsh 4.15.2，numpy；无联网步骤）：
    "$TMPDIR/rearm-gripper-venv/bin/python" scripts/build_gripper_mesh.py

与 b601 相同：小端 float32 positions、uint32 indices，连续写入，无额外头部。
尺寸按 STEP 的 mm 转为 m；安装参数唯一来源为 arm-params.js。
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
STEP = ROOT / "hardware/gripper/机械臂夹具.STEP"
PARAMS = ROOT / "rearm/ui/static/modules/arm/arm-params.js"
OUT = ROOT / "rearm/ui/static/modules/twin/meshes"


def read_mount():
    """只读取声明为数字字面量的安装参数，不执行 JavaScript。"""
    source = re.sub(r"//[^\n]*", "", PARAMS.read_text(encoding="utf-8"))
    block = re.search(r"customFinger:\s*\{(.*?)\n\s*\},", source, re.S).group(1)
    mount = re.search(r"mount:\s*\{([^}]+)\}", block).group(1)
    array = lambda text, key: json.loads(re.search(rf"\b{key}:\s*(\[[^]]+\])", text).group(1))
    return {"mount": {key: array(mount, key) for key in ("xyz", "rpy")},
            "flipRpy": array(block, "flipRpy"),
            "tipX": float(re.search(r"tipX:\s*([-+\d.eE]+)", block).group(1))}


def rotation(rpy):
    """URDF 固定轴 RPY：Rz(yaw) @ Ry(pitch) @ Rx(roll)。"""
    r, p, y = rpy
    sr, sp, sy = np.sin([r, p, y])
    cr, cp, cy = np.cos([r, p, y])
    return np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                     [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                     [-sp, cp * sr, cp * cr]])


def tessellate():
    import gmsh

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.NumThreads", 1)
        gmsh.option.setString("Geometry.OCCTargetUnit", "MM")
        gmsh.model.occ.importShapes(str(STEP))
        gmsh.model.occ.synchronize()
        volumes = gmsh.model.getEntities(3)
        if len(volumes) != 1:
            raise ValueError(f"预期单个实体，实际 {len(volumes)} 个")
        bounds = np.array(gmsh.model.getBoundingBox(*volumes[0])).reshape(2, 3)
        # 平面保留矩形开孔；圆孔每周至少约 20 段，两指合计约 6000 面。
        gmsh.option.setNumber("Mesh.MeshSizeMin", 2)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 4)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 20)
        gmsh.option.setNumber("Mesh.ElementOrder", 1)
        gmsh.option.setNumber("Mesh.RecombineAll", 0)
        gmsh.option.setNumber("Mesh.RandomSeed", 1)
        gmsh.model.mesh.generate(2)
        tags, coords, _ = gmsh.model.mesh.getNodes()
        types, _, nodes = gmsh.model.mesh.getElements(2)
        if list(types) != [2]:
            raise ValueError(f"需要一阶三角形，实际单元类型 {list(types)}")
        # 节点标签不保证连续或有序，显式重映射为零起始索引。
        order = np.argsort(tags)
        indices = order[np.searchsorted(tags[order], nodes[0])].reshape(-1, 3)
        points = np.asarray(coords).reshape(-1, 3)
        used, inverse = np.unique(indices, return_inverse=True)
        return points[used], inverse.reshape(-1, 3), bounds.round(6), gmsh.__version__
    finally:
        gmsh.finalize()


def main(output=OUT):
    assembly = read_mount()
    points, triangles, bounds, version = tessellate()
    if len(triangles) * 2 >= 20_000:
        raise ValueError(f"两指共 {len(triangles) * 2} 面，超出预算")
    left = points / 1000 @ rotation(assembly["mount"]["rpy"]).T + assembly["mount"]["xyz"]
    right = left @ rotation(assembly["flipRpy"]).T
    if abs(left[:, 0].max() - assembly["tipX"]) > 1e-6:
        raise ValueError("安装后的指尖与 customFinger.tipX 不一致")
    parts, blobs, offset = [], [], 0
    for side, vertices, material in (("left", left, "finger_white"), ("right", right, "finger_grey")):
        part = {"frame": "tool", "source": "custom_finger_" + side, "side": side, "material": material}
        for key, array in (("positions", vertices.astype("<f4")), ("indices", triangles.astype("<u4"))):
            blob = array.tobytes()
            part[key] = {"offset": offset, "count": int(array.size)}
            blobs.append(blob)
            offset += len(blob)
        parts.append(part)
    manifest = {
        "model": "ReArm 自制矩形夹指", "units": "m", "simplified": False,
        "triangles": len(triangles) * 2, "source": str(STEP.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(STEP.read_bytes()).hexdigest(),
        "generator": f"gmsh {version} / OpenCASCADE; mesh min 2 mm, max 4 mm, curvature 20",
        "step_bounds_mm": {"min": bounds[0].tolist(), "max": bounds[1].tolist(),
                           "size": (bounds[1] - bounds[0]).tolist()},
        "assembly": assembly, "opening_mm": 0,
        "note": "照片估算安装；STEP +Z 伸出，Z=0 四孔根面贴滑块。右指绕 end_link X 翻转 180°。",
        "parts": parts,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "gripper.bin").write_bytes(b"".join(blobs))
    (output / "gripper.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"STEP bbox (mm): {manifest['step_bounds_mm']}")
    print(f"2 parts, {manifest['triangles']} triangles, {offset} bytes; simplified=false")
    print(f"mount={assembly}; output={output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output-dir", type=Path, default=OUT)
    main(parser.parse_args().output_dir)

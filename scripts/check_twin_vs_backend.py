"""只读核对前端与指定后端的夹头/相机完整位姿，不连接或驱动硬件。

.venv/bin/python scripts/check_twin_vs_backend.py /path/to/backend
可选 --baseline-params /path/to/old-arm-params.js 保存改前比较；--output 指定报告。
后端在独立 Python 子进程中导入，-B 禁止写入其 __pycache__；不会提交或复制后端代码。
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "rearm/ui/static/modules"
FIXTURE = ROOT / "docs/路演/接口核对/FK对照.json"
WORK_Q = [1.6405, -1.6608, -2.2757, 1.8915, -0.0063, 0.1276]
# 渲染 X前/Y左/Z上 -> OpenCV x右/y下/z前，列是渲染轴在 OpenCV 中的表示。
CV_FROM_RENDER = np.array([[0, -1, 0, 0], [0, 0, -1, 0], [1, 0, 0, 0], [0, 0, 0, 1.]])


def frontend(poses, params_path):
    code = f"""
import {{ARM_PARAMS as p}} from {json.dumps(params_path.resolve().as_uri())};
import {{endPoses, frustumCorners}} from './arm/fk.js';
const qs = {json.dumps(poses)};
console.log(JSON.stringify({{params:p, poses:qs.map(q => ({{...endPoses(p,q), corners:frustumCorners(p,q)}}))}}));
"""
    result = subprocess.run(["node", "--input-type=module", "-e", code], cwd=MODULES,
                            check=True, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)


def backend_data(backend, poses):
    python = backend / ".venv/bin/python"
    if not python.is_file():
        python = Path(sys.executable)
    code = """
import json, sys
from pathlib import Path
import numpy as np
from rearm.task import pick
from rearm.model import kin6
qs = json.load(sys.stdin)
params = kin6._validated_params(kin6.nominal())
print(json.dumps({
 'poses': [{'tip':pick.frames(np.asarray(q))[1].tolist(),
            'kin6_tool_offset_frame':kin6._tcp_transform(np.asarray(q), params).tolist()} for q in qs],
 'handeye':json.loads(Path('config/handeye_camera.json').read_text()),
 'gripper':json.loads(Path('config/gripper.json').read_text()),
 'closing_axis':pick.CLOSING_AXIS, 'table_tip_z_mm':pick.TABLE_TIP_Z_MM,
 'tool_x_mm':params['tool_x'],
}))
"""
    result = subprocess.run([str(python), "-B", "-c", code], cwd=backend,
                            input=json.dumps(poses), check=True, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)


def matrix_mm(flat):
    matrix = np.asarray(flat, dtype=float).reshape(4, 4).copy()
    matrix[:3, 3] *= 1000
    return matrix


def rotation(matrix):
    # 手眼矩阵只有六位小数，近似正交；仅在角度度量时投影 SO(3)，报告原矩阵不改。
    u, _, vt = np.linalg.svd(matrix[:3, :3])
    return u @ np.diag([1, 1, np.linalg.det(u @ vt)]) @ vt


def error(actual, expected):
    relative = rotation(actual) @ rotation(expected).T
    sine = np.linalg.norm([relative[2, 1] - relative[1, 2], relative[0, 2] - relative[2, 0],
                           relative[1, 0] - relative[0, 1]]) / 2
    angle = np.degrees(np.arctan2(sine, (np.trace(relative) - 1) / 2))
    return {"position_mm": float(np.linalg.norm(actual[:3, 3] - expected[:3, 3])),
            "orientation_deg": float(angle),
            "rotation_max_abs": float(np.abs(actual[:3, :3] - expected[:3, :3]).max()),
            "homogeneous_row_max_abs": float(np.abs(actual[3] - expected[3]).max())}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(backend, baseline=None):
    qs = [row["q"] for row in json.loads(FIXTURE.read_text())["poses"]] + [WORK_Q]
    current = frontend(qs, MODULES / "arm/arm-params.js")
    old = frontend(qs, baseline) if baseline else None
    back = backend_data(backend, qs)
    tip_cam = np.array(back["handeye"]["T_tip_cam"])
    rows = []
    for i, (q, f, b) in enumerate(zip(qs, current["poses"], back["poses"])):
        tip = np.array(b["tip"])
        end, tcp, camera = (matrix_mm(f[k]) for k in ("end_link", "tcp", "camera"))
        expected_camera = tip @ tip_cam
        # 用完整 OpenCV 位姿比较，包含光轴和画面横/纵轴，不只比光轴。
        camera_cv = camera @ CV_FROM_RENDER.T
        center = np.mean(f["corners"], axis=0) * 1000
        axis = camera[:3, 0] / np.linalg.norm(camera[:3, 0])
        ray = center - camera[:3, 3]
        row = {"name": f"FK样例{i + 1}" if i < 3 else "真机工作位", "q_rad": q,
               "frontend_end_link_mm": end.tolist(), "backend_tip_mm": tip.tolist(),
               "T_end_tip_required_mm": (np.linalg.inv(end) @ tip).tolist(),
               "end_link_vs_tip": error(end, tip),
               "frontend_tcp_mm": tcp.tolist(), "tcp_vs_tip": error(tcp, tip),
               "frontend_camera_render_mm": camera.tolist(), "frontend_camera_opencv_mm": camera_cv.tolist(),
               "backend_camera_opencv_mm": expected_camera.tolist(), "camera_vs_backend": error(camera_cv, expected_camera),
               "frustum_center_ray_error_deg": float(np.degrees(np.arctan2(np.linalg.norm(np.cross(ray, axis)), ray @ axis))),
               "kin6_tool_offset_frame_mm": b["kin6_tool_offset_frame"],
               "kin6_offset_to_tip_mm": float(np.linalg.norm(np.array(b["kin6_tool_offset_frame"])[:3, 3] - tip[:3, 3]))}
        if old:
            row["before"] = {"tcp_vs_tip": error(matrix_mm(old["poses"][i]["tcp"]), tip),
                             "camera_vs_backend": error(matrix_mm(old["poses"][i]["camera"]) @ CV_FROM_RENDER.T, expected_camera)}
        rows.append(row)
    summary = {key: {field: max(r[key][field] for r in rows) for field in rows[0][key]}
               for key in ("end_link_vs_tip", "tcp_vs_tip", "camera_vs_backend")}
    passed = all(r[key]["position_mm"] < 0.5 and r[key]["orientation_deg"] < 0.5
                 and r[key]["homogeneous_row_max_abs"] < 1e-12
                 for r in rows for key in summary)
    passed = passed and all(r["frustum_center_ray_error_deg"] < 0.5 for r in rows)
    sources = ["rearm/model/kin6.py", "rearm/task/pick.py", "config/handeye_camera.json", "config/gripper.json"]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=backend, capture_output=True, text=True, check=True).stdout.strip()
    params = current["params"]
    report = {"pure_calculation_only": True, "passed": passed,
              "thresholds": {"position_mm": 0.5, "orientation_deg": 0.5},
              "units": "4x4 行主序；报告平移 mm，旋转无量纲，关节 rad，误差角度 deg",
              "reference": "pick.frames(q)[1] = base·DH1..6·TOOL_DH；不含 kin6 tool_x",
              "closing_axis": back["closing_axis"], "table_tip_z_mm": back["table_tip_z_mm"],
              "tool_x_mm": back["tool_x_mm"], "CV_from_render": CV_FROM_RENDER.tolist(),
              "angle_metric": "SVD 投影 SO(3) 后 atan2；不修改原始手眼矩阵的六位小数",
              "T_tip_cam_mm": tip_cam.tolist(), "T_end_tcp_m": params["T_end_tcp"],
              "T_end_camera_m": params["T_end_camera"], "summary_max_errors": summary, "poses": rows,
              "gripper": {"frontend": params["gripper"]["finger"],
                          "backend": {k: back["gripper"][k] for k in ("finger_thickness_mm", "v_diamond_side_mm", "v_angle_deg", "v_depth_mm", "v_mouth_mm", "tip_flat_height_mm", "max_open_mm")},
                          "unconfirmed": "长度待尺量；外宽 25 mm 沿用 STEP；孔位细节未表示"},
              "sources": {"backend_commit": commit, "backend_sha256": {p: sha(backend / p) for p in sources},
                          "frontend_params_sha256": sha(MODULES / "arm/arm-params.js"), "fixture_sha256": sha(FIXTURE)},
              "limits": {"hardware_executed": False, "handeye_caveats": back["handeye"]["caveats"],
                         "handeye_solve_rms_mm": back["handeye"]["source"]["solve_rms_mm"],
                         "camera_case": "外壳尺寸仍为估算，未由手眼矩阵确认"}}
    if old:
        report["before_parameters"] = {k: old["params"][k] for k in ("T_end_tcp", "T_end_camera", "gripper", "shape")}
        report["sources"]["baseline_params_sha256"] = sha(baseline)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backend", type=Path)
    parser.add_argument("--baseline-params", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/路演/接口核对/孪生对照.json")
    args = parser.parse_args()
    report = check(args.backend.resolve(), args.baseline_params)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "summary_max_errors": report["summary_max_errors"],
                      "output": str(args.output)}, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

import glob
import json
import os
import cv2
import mediapipe as mp
import urllib.request
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision
import numpy as np

# 20 exercises matching your exact filenames in raw_gold_videos/{45_degree, side, front}
EXERCISE_SPECS = {
    "bench_press": {
        "name": "Bench Press",
        "mode": "dynamic",
        "primary_joint": "left_elbow",
        "weights": {
            "left_elbow": 1.0,
            "right_elbow": 1.0,
            "left_shoulder": 0.9,
            "right_shoulder": 0.9,
            "torso_lean": 0.6,
        },
        "rules": {
            "max_bottom_elbow_angle": 90.0,
            "min_torso_lean": 70.0,
        },
    },
    "incline_bench_press": {
        "name": "Incline Bench Press",
        "mode": "dynamic",
        "primary_joint": "left_elbow",
        "weights": {
            "left_elbow": 1.0,
            "right_elbow": 1.0,
            "left_shoulder": 0.9,
            "right_shoulder": 0.9,
            "torso_lean": 0.6,
        },
        "rules": {
            "max_bottom_elbow_angle": 90.0,
            "min_torso_lean": 30.0,
            "max_torso_lean": 65.0,
        },
    },
    "chest_fly_machine": {
        "name": "Chest Fly Machine",
        "mode": "dynamic",
        "primary_joint": "left_shoulder",
        "weights": {
            "left_shoulder": 1.0,
            "right_shoulder": 1.0,
            "left_elbow": 0.7,
            "right_elbow": 0.7,
            "shoulder_symmetry": 0.6,
        },
        "rules": {
            "min_elbow_angle": 135.0,
        },
    },
    "bicep_curl": {
        "name": "Bicep Curl",
        "mode": "dynamic",
        "primary_joint": "left_elbow",
        "weights": {
            "left_elbow": 1.0,
            "right_elbow": 1.0,
            "left_shoulder": 0.7,
            "right_shoulder": 0.7,
            "torso_lean": 0.6,
        },
        "rules": {
            "max_peak_elbow_angle": 55.0,
            "max_torso_lean": 20.0,
        },
    },
    "hammer_curl": {
        "name": "Hammer Curl",
        "mode": "dynamic",
        "primary_joint": "left_elbow",
        "weights": {
            "left_elbow": 1.0,
            "right_elbow": 1.0,
            "left_shoulder": 0.7,
            "right_shoulder": 0.7,
            "torso_lean": 0.6,
        },
        "rules": {
            "max_peak_elbow_angle": 60.0,
            "max_torso_lean": 20.0,
        },
    },
    "conv_deadlift": {
        "name": "Conventional Deadlift",
        "mode": "dynamic",
        "primary_joint": "left_hip",
        "weights": {
            "left_hip": 1.0,
            "right_hip": 1.0,
            "left_knee": 0.8,
            "right_knee": 0.8,
            "torso_lean": 0.9,
        },
        "rules": {
            "min_lockout_hip_angle": 165.0,
            "max_torso_lean": 75.0,
        },
    },
    "sumo_deadlift": {
        "name": "Sumo Deadlift",
        "mode": "dynamic",
        "primary_joint": "left_hip",
        "weights": {
            "left_hip": 1.0,
            "right_hip": 1.0,
            "left_knee": 0.9,
            "right_knee": 0.9,
            "torso_lean": 0.8,
            "hip_symmetry": 0.6,
        },
        "rules": {
            "min_lockout_hip_angle": 165.0,
            "max_torso_lean": 60.0,
        },
    },
    "romanian_deadlift": {
        "name": "Romanian Deadlift",
        "mode": "dynamic",
        "primary_joint": "left_hip",
        "weights": {
            "left_hip": 1.0,
            "right_hip": 1.0,
            "left_knee": 0.7,
            "right_knee": 0.7,
            "torso_lean": 0.9,
        },
        "rules": {
            "min_bottom_knee_angle": 140.0,
            "min_lockout_hip_angle": 165.0,
        },
    },
    "hip_thrust": {
        "name": "Hip Thrust",
        "mode": "dynamic",
        "primary_joint": "left_hip",
        "weights": {
            "left_hip": 1.0,
            "right_hip": 1.0,
            "left_knee": 0.8,
            "right_knee": 0.8,
            "torso_lean": 0.6,
        },
        "rules": {
            "min_lockout_hip_angle": 165.0,
        },
    },
    "lat_pulldown": {
        "name": "Lat Pulldown",
        "mode": "dynamic",
        "primary_joint": "left_elbow",
        "weights": {
            "left_elbow": 1.0,
            "right_elbow": 1.0,
            "left_shoulder": 0.9,
            "right_shoulder": 0.9,
            "torso_lean": 0.5,
            "shoulder_symmetry": 0.6,
        },
        "rules": {
            "max_bottom_elbow_angle": 75.0,
            "max_torso_lean": 30.0,
        },
    },
    "pull_up": {
        "name": "Pull-Up",
        "mode": "dynamic",
        "primary_joint": "left_elbow",
        "weights": {
            "left_elbow": 1.0,
            "right_elbow": 1.0,
            "left_shoulder": 0.9,
            "right_shoulder": 0.9,
            "shoulder_symmetry": 0.6,
        },
        "rules": {
            "max_top_elbow_angle": 75.0,
        },
    },
    "t_bar_row": {
        "name": "T-Bar Row",
        "mode": "dynamic",
        "primary_joint": "left_elbow",
        "weights": {
            "left_elbow": 1.0,
            "right_elbow": 1.0,
            "left_shoulder": 0.8,
            "right_shoulder": 0.8,
            "torso_lean": 0.8,
        },
        "rules": {
            "min_torso_lean": 30.0,
            "max_torso_lean": 65.0,
        },
    },
    "lateral_raise": {
        "name": "Lateral Raise",
        "mode": "dynamic",
        "primary_joint": "left_shoulder",
        "weights": {
            "left_shoulder": 1.0,
            "right_shoulder": 1.0,
            "left_elbow": 0.6,
            "right_elbow": 0.6,
            "torso_lean": 0.5,
            "shoulder_symmetry": 0.7,
        },
        "rules": {
            "min_peak_shoulder_angle": 75.0,
            "max_torso_lean": 20.0,
        },
    },
    "shoulder_press": {
        "name": "Shoulder Press",
        "mode": "dynamic",
        "primary_joint": "left_elbow",
        "weights": {
            "left_elbow": 1.0,
            "right_elbow": 1.0,
            "left_shoulder": 0.9,
            "right_shoulder": 0.9,
            "torso_lean": 0.6,
            "shoulder_symmetry": 0.6,
        },
        "rules": {
            "min_lockout_elbow_angle": 160.0,
            "max_torso_lean": 25.0,
        },
    },
    "leg_extension": {
        "name": "Leg Extension",
        "mode": "dynamic",
        "primary_joint": "left_knee",
        "weights": {
            "left_knee": 1.0,
            "right_knee": 1.0,
            "left_hip": 0.6,
            "right_hip": 0.6,
            "torso_lean": 0.5,
        },
        "rules": {
            "min_lockout_knee_angle": 160.0,
        },
    },
    "squat": {
        "name": "Squat",
        "mode": "dynamic",
        "primary_joint": "left_knee",
        "weights": {
            "left_knee": 1.0,
            "right_knee": 1.0,
            "left_hip": 0.9,
            "right_hip": 0.9,
            "torso_lean": 0.7,
            "hip_symmetry": 0.5,
        },
        "rules": {
            "max_bottom_knee_angle": 100.0,
            "max_torso_lean": 50.0,
        },
    },
    "plank": {
        "name": "Plank",
        "mode": "isometric",
        "primary_joint": "left_hip",
        "weights": {
            "left_hip": 1.0,
            "right_hip": 1.0,
            "left_knee": 0.8,
            "right_knee": 0.8,
            "torso_lean": 0.8,
        },
        "rules": {
            "min_hip_angle": 160.0,
            "min_knee_angle": 160.0,
            "min_torso_lean": 70.0,
            "max_torso_lean": 105.0,
        },
    },
    "push_up": {
        "name": "Push-Up",
        "mode": "dynamic",
        "primary_joint": "left_elbow",
        "weights": {
            "left_elbow": 1.0,
            "right_elbow": 1.0,
            "left_hip": 0.8,
            "right_hip": 0.8,
            "torso_lean": 0.6,
        },
        "rules": {
            "max_bottom_elbow_angle": 95.0,
            "min_hip_angle": 155.0,
        },
    },
    "tricep_dips": {
        "name": "Tricep Dips",
        "mode": "dynamic",
        "primary_joint": "left_elbow",
        "weights": {
            "left_elbow": 1.0,
            "right_elbow": 1.0,
            "left_shoulder": 0.8,
            "right_shoulder": 0.8,
            "torso_lean": 0.5,
        },
        "rules": {
            "max_bottom_elbow_angle": 95.0,
        },
    },
    "tricep_pushdown": {
        "name": "Tricep Pushdown",
        "mode": "dynamic",
        "primary_joint": "left_elbow",
        "weights": {
            "left_elbow": 1.0,
            "right_elbow": 1.0,
            "left_shoulder": 0.8,
            "right_shoulder": 0.8,
            "torso_lean": 0.5,
        },
        "rules": {
            "min_lockout_elbow_angle": 160.0,
            "max_torso_lean": 30.0,
        },
    },
}

ANGLE_KEYS = [
    "left_elbow",
    "right_elbow",
    "left_shoulder",
    "right_shoulder",
    "left_knee",
    "right_knee",
    "left_hip",
    "right_hip",
    "torso_lean",
    "left_ankle",
    "right_ankle",
    "hip_symmetry",
    "shoulder_symmetry",
    "torso_lateral_tilt",
]


def calc_angle_3d(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ba = a - b
    bc = c - b
    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)
    if norm_ba < 1e-6 or norm_bc < 1e-6:
        return 0.0
    cosine = np.clip(np.dot(ba, bc) / (norm_ba * norm_bc), -1.0, 1.0)
    return float(np.degrees(np.arccos(cosine)))


def extract_14_angles(world_landmarks) -> dict:
    pts = np.array([[lm.x, lm.y, lm.z] for lm in world_landmarks], dtype=np.float32)

    l_sh, r_sh = pts[11], pts[12]
    l_el, r_el = pts[13], pts[14]
    l_wr, r_wr = pts[15], pts[16]
    l_hip, r_hip = pts[23], pts[24]
    l_kn, r_kn = pts[25], pts[26]
    l_an, r_an = pts[27], pts[28]
    l_ft, r_ft = pts[31], pts[32]

    mid_sh = (l_sh + r_sh) * 0.5
    mid_hip = (l_hip + r_hip) * 0.5
    spine = mid_sh - mid_hip
    vertical_up = np.array([0.0, -1.0, 0.0], dtype=np.float32)

    spine_norm = np.linalg.norm(spine)
    torso_lean = (
        float(np.degrees(np.arccos(np.clip(np.dot(spine, vertical_up) / spine_norm, -1.0, 1.0))))
        if spine_norm > 1e-6
        else 0.0
    )

    # Frontal/coronal symmetry angles (degrees of tilt from horizontal)
    hip_vec = r_hip - l_hip
    sh_vec = r_sh - l_sh
    hip_sym = float(np.degrees(np.arctan2(abs(hip_vec[1]), max(np.hypot(hip_vec[0], hip_vec[2]), 1e-6))))
    sh_sym = float(np.degrees(np.arctan2(abs(sh_vec[1]), max(np.hypot(sh_vec[0], sh_vec[2]), 1e-6))))
    lat_tilt = float(np.degrees(np.arctan2(abs(spine[0]), max(abs(spine[1]), 1e-6))))

    return {
        "left_elbow": calc_angle_3d(l_sh, l_el, l_wr),
        "right_elbow": calc_angle_3d(r_sh, r_el, r_wr),
        "left_shoulder": calc_angle_3d(l_hip, l_sh, l_el),
        "right_shoulder": calc_angle_3d(r_hip, r_sh, r_el),
        "left_knee": calc_angle_3d(l_hip, l_kn, l_an),
        "right_knee": calc_angle_3d(r_hip, r_kn, r_an),
        "left_hip": calc_angle_3d(l_sh, l_hip, l_kn),
        "right_hip": calc_angle_3d(r_sh, r_hip, r_kn),
        "torso_lean": torso_lean,
        "left_ankle": calc_angle_3d(l_kn, l_an, l_ft),
        "right_ankle": calc_angle_3d(r_kn, r_an, r_ft),
        "hip_symmetry": hip_sym,
        "shoulder_symmetry": sh_sym,
        "torso_lateral_tilt": lat_tilt,
    }


def smooth_and_resample(series_list: list[dict], target_frames: int = 60) -> dict:
    n = len(series_list)
    if n < 2:
        raise ValueError("Video must have at least 2 valid pose frames.")

    x_old = np.linspace(0.0, 1.0, n)
    x_new = np.linspace(0.0, 1.0, target_frames)
    kernel = np.ones(5, dtype=np.float32) / 5.0

    curves = {}
    for key in ANGLE_KEYS:
        raw = np.array([frame[key] for frame in series_list], dtype=np.float32)
        if n >= 5:
            padded = np.pad(raw, (2, 2), mode="edge")
            raw = np.convolve(padded, kernel, mode="valid")
        resampled = np.interp(x_new, x_old, raw)
        curves[key] = [round(float(v), 2) for v in resampled]
    return curves

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task"
)


def ensure_pose_model(script_dir: str) -> str:
    model_path = os.path.join(script_dir, "pose_landmarker_heavy.task")
    if not os.path.exists(model_path):
        print("Downloading pose_landmarker_heavy.task (one-time ~30MB)...")
        urllib.request.urlretrieve(MODEL_URL, model_path)
    return model_path

def process_video(video_path: str, landmarker, target_frames: int = 60) -> dict:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames_angles = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = int((frame_idx * 1000.0) / fps)
        frame_idx += 1

        results = landmarker.detect_for_video(mp_image, timestamp_ms)
        if results.pose_world_landmarks:
            frames_angles.append(extract_14_angles(results.pose_world_landmarks[0]))

    cap.release()

    if len(frames_angles) < 5:
        raise RuntimeError(f"Too few detected pose frames ({len(frames_angles)}) in {video_path}")

    return smooth_and_resample(frames_angles, target_frames=target_frames)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    base_dir = os.path.join(project_root, "raw_gold_videos")
    output_dir = os.path.join(project_root, "workouts", "static", "workouts", "gold_forms")
    os.makedirs(output_dir, exist_ok=True)

    model_path = ensure_pose_model(script_dir)

    grouped_clips = {}
    for view in ["45_degree", "side", "front"]:
        view_dir = os.path.join(base_dir, view)
        if not os.path.isdir(view_dir):
            continue
        for video_path in sorted(glob.glob(os.path.join(view_dir, "*.mp4"))):
            slug = os.path.splitext(os.path.basename(video_path))[0].lower()
            if slug not in EXERCISE_SPECS:
                print(f"[SKIP] {view}/{slug}.mp4 (not in EXERCISE_SPECS)")
                continue
            grouped_clips.setdefault(slug, []).append((view, video_path))

    base_options = mp_tasks.BaseOptions(model_asset_path=model_path)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    for slug, clips in sorted(grouped_clips.items()):
        spec = EXERCISE_SPECS[slug]
        templates = []
        for view, video_path in clips:
            try:
                # Fresh landmarker per video resets monotonic video timestamps cleanly
                with vision.PoseLandmarker.create_from_options(options) as landmarker:
                    curves = process_video(video_path, landmarker, target_frames=60)
                    templates.append({
                        "view": view,
                        "reference_angles": curves,
                    })
            except Exception as exc:
                print(f"[ERROR] {view}/{slug}.mp4 -> {exc}")

        if not templates:
            continue

        payload = {
            "slug": slug,
            "exercise": spec["name"],
            "mode": spec.get("mode", "dynamic"),
            "frames": 60,
            "primary_joint": spec["primary_joint"],
            "weights": spec["weights"],
            "rules": spec["rules"],
            "templates": templates,
        }
        out_file = os.path.join(output_dir, f"{slug}.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        views_str = ", ".join(t["view"] for t in templates)
        print(f"[OK] {slug}.json ({len(templates)} views: {views_str})")


if __name__ == "__main__":
    main()
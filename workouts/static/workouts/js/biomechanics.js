window.Biomechanics = (function () {
  const VISIBILITY_THRESHOLD = 0.7;

  // 10 Triplet Joint Angles (MediaPipe 33-point indices)
  const ANGLE_DEFINITIONS = {
    left_elbow:     [11, 13, 15], // Shoulder -> Elbow -> Wrist
    right_elbow:    [12, 14, 16],
    left_shoulder:  [23, 11, 13], // Hip -> Shoulder -> Elbow
    right_shoulder: [24, 12, 14],
    left_hip:       [11, 23, 25], // Shoulder -> Hip -> Knee
    right_hip:      [12, 24, 26],
    left_knee:      [23, 25, 27], // Hip -> Knee -> Ankle
    right_knee:     [24, 26, 28],
    left_ankle:     [25, 27, 31], // Knee -> Ankle -> Foot Index
    right_ankle:    [26, 28, 32],
  };

  function getVis(worldPt, normPt) {
    // Prefer 2D poseLandmarks visibility (always populated); fallback to worldPt
    if (normPt && typeof normPt.visibility === "number") return normPt.visibility;
    if (worldPt && typeof worldPt.visibility === "number") return worldPt.visibility;
    return 1.0;
  }

  function calculateAngle3D(worldPts, normPts, iA, iB, iC) {
    const a = worldPts[iA], b = worldPts[iB], c = worldPts[iC];
    if (!a || !b || !c) return null;

    const minVis = Math.min(
      getVis(a, normPts?.[iA]),
      getVis(b, normPts?.[iB]),
      getVis(c, normPts?.[iC])
    );
    if (minVis < VISIBILITY_THRESHOLD) return null; // Occluded joint gate

    const ba = { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
    const bc = { x: c.x - b.x, y: c.y - b.y, z: c.z - b.z };

    const dot = ba.x * bc.x + ba.y * bc.y + ba.z * bc.z;
    const magBA = Math.hypot(ba.x, ba.y, ba.z);
    const magBC = Math.hypot(bc.x, bc.y, bc.z);
    if (magBA < 1e-6 || magBC < 1e-6) return null;

    const cosAngle = Math.max(-1, Math.min(1, dot / (magBA * magBC)));
    return Number(((Math.acos(cosAngle) * 180) / Math.PI).toFixed(2));
  }

  function calculateTorsoAndSymmetry(worldPts, normPts) {
    const lSh = worldPts[11], rSh = worldPts[12];
    const lHip = worldPts[23], rHip = worldPts[24];
    if (!lSh || !rSh || !lHip || !rHip) {
      return { torso_lean: null, hip_symmetry: null, shoulder_symmetry: null, torso_lateral_tilt: null };
    }

    const vLSh = getVis(lSh, normPts?.[11]);
    const vRSh = getVis(rSh, normPts?.[12]);
    const vLHip = getVis(lHip, normPts?.[23]);
    const vRHip = getVis(rHip, normPts?.[24]);

    const leftOk = vLSh >= VISIBILITY_THRESHOLD && vLHip >= VISIBILITY_THRESHOLD;
    const rightOk = vRSh >= VISIBILITY_THRESHOLD && vRHip >= VISIBILITY_THRESHOLD;

    if (!leftOk && !rightOk) {
      return { torso_lean: null, hip_symmetry: null, shoulder_symmetry: null, torso_lateral_tilt: null };
    }

    // Use bilateral midpoint when both sides are visible; fallback to visible side in 90° side views
    let spine;
    if (leftOk && rightOk) {
      const midSh = { x: (lSh.x + rSh.x) * 0.5, y: (lSh.y + rSh.y) * 0.5, z: (lSh.z + rSh.z) * 0.5 };
      const midHip = { x: (lHip.x + rHip.x) * 0.5, y: (lHip.y + rHip.y) * 0.5, z: (lHip.z + rHip.z) * 0.5 };
      spine = { x: midSh.x - midHip.x, y: midSh.y - midHip.y, z: midSh.z - midHip.z };
    } else if (leftOk) {
      spine = { x: lSh.x - lHip.x, y: lSh.y - lHip.y, z: lSh.z - lHip.z };
    } else {
      spine = { x: rSh.x - rHip.x, y: rSh.y - rHip.y, z: rSh.z - rHip.z };
    }

    const spineNorm = Math.hypot(spine.x, spine.y, spine.z);
    const torso_lean = spineNorm > 1e-6
      ? Number(((Math.acos(Math.max(-1, Math.min(1, -spine.y / spineNorm))) * 180) / Math.PI).toFixed(2))
      : null;

    // Frontal/coronal symmetry angles (degrees of tilt from horizontal — matches extract_gold.py)
    let hip_symmetry = null;
    if (vLHip >= VISIBILITY_THRESHOLD && vRHip >= VISIBILITY_THRESHOLD) {
      const hipVec = { x: rHip.x - lHip.x, y: rHip.y - lHip.y, z: rHip.z - lHip.z };
      hip_symmetry = Number(
        ((Math.atan2(Math.abs(hipVec.y), Math.max(Math.hypot(hipVec.x, hipVec.z), 1e-6)) * 180) / Math.PI).toFixed(2)
      );
    }

    let shoulder_symmetry = null;
    if (vLSh >= VISIBILITY_THRESHOLD && vRSh >= VISIBILITY_THRESHOLD) {
      const shVec = { x: rSh.x - lSh.x, y: rSh.y - lSh.y, z: rSh.z - lSh.z };
      shoulder_symmetry = Number(
        ((Math.atan2(Math.abs(shVec.y), Math.max(Math.hypot(shVec.x, shVec.z), 1e-6)) * 180) / Math.PI).toFixed(2)
      );
    }

    const torso_lateral_tilt = spineNorm > 1e-6
      ? Number(((Math.atan2(Math.abs(spine.x), Math.max(Math.abs(spine.y), 1e-6)) * 180) / Math.PI).toFixed(2))
      : null;

    return { torso_lean, hip_symmetry, shoulder_symmetry, torso_lateral_tilt };
  }

  function extractAllAngles(worldLandmarks, normLandmarks = null) {
    if (!worldLandmarks || !Array.isArray(worldLandmarks)) return null;

    const angles = {};
    for (const [name, [iA, iB, iC]] of Object.entries(ANGLE_DEFINITIONS)) {
      angles[name] = calculateAngle3D(worldLandmarks, normLandmarks, iA, iB, iC);
    }

    const torsoMetrics = calculateTorsoAndSymmetry(worldLandmarks, normLandmarks);
    return { ...angles, ...torsoMetrics };
  }

  return { extractAllAngles, VISIBILITY_THRESHOLD };
})();
// workouts/static/workouts/js/dtw_engine.js
window.DTWEngine = (function () {
  const TARGET_FRAMES = 60;
  const DEFAULT_BASE_URL = "/static/workouts/gold_forms";

  function resampleCurve(values, targetLen = TARGET_FRAMES) {
    const n = values.length;
    if (n === 0) return [];
    if (n === 1) return Array(targetLen).fill(values[0]);

    const out = new Array(targetLen);
    for (let i = 0; i < targetLen; i++) {
      const pos = (i * (n - 1)) / (targetLen - 1);
      const lo = Math.floor(pos);
      const hi = Math.min(n - 1, lo + 1);
      const frac = pos - lo;
      out[i] = values[lo] * (1 - frac) + values[hi] * frac;
    }
    return out;
  }

  // Sakoe-Chiba banded 1D Dynamic Time Warping distance (mean per-step degree error)
  function dtwDistance1D(seqA, seqB, bandRatio = 0.25) {
    const n = seqA.length;
    const m = seqB.length;
    if (!n || !m) return Infinity;

    const band = Math.max(5, Math.ceil(Math.max(n, m) * bandRatio));
    const INF = 1e9;
    let prev = new Float64Array(m + 1).fill(INF);
    let curr = new Float64Array(m + 1).fill(INF);
    prev[0] = 0;

    for (let i = 1; i <= n; i++) {
      curr.fill(INF);
      const jCenter = Math.round((i * m) / n);
      const jStart = Math.max(1, jCenter - band);
      const jEnd = Math.min(m, jCenter + band);

      for (let j = jStart; j <= jEnd; j++) {
        const cost = Math.abs(seqA[i - 1] - seqB[j - 1]);
        const bestPrev = Math.min(prev[j], curr[j - 1], prev[j - 1]);
        curr[j] = cost + bestPrev;
      }
      const tmp = prev;
      prev = curr;
      curr = tmp;
    }

    return prev[m] / Math.max(n, m);
  }

  function extractValidSeries(frameBuffer, jointKey) {
    const vals = [];
    for (let i = 0; i < frameBuffer.length; i++) {
      const v = frameBuffer[i]?.angles?.[jointKey];
      if (typeof v === "number" && !Number.isNaN(v)) {
        vals.push(v);
      }
    }
    return vals;
  }

  function rangeOf(arr) {
    if (!arr || arr.length < 2) return 0;
    let min = Infinity;
    let max = -Infinity;
    for (let i = 0; i < arr.length; i++) {
      if (arr[i] < min) min = arr[i];
      if (arr[i] > max) max = arr[i];
    }
    return max - min;
  }

  function evaluateRules(frameBuffer, rules, activeMode) {
    const cues = [];
    if (!rules || !frameBuffer.length) return cues;

    const getStats = (key) => {
      const vals = extractValidSeries(frameBuffer, key);
      if (!vals.length) return null;
      return {
        min: Math.min(...vals),
        max: Math.max(...vals),
        avg: vals.reduce((a, b) => a + b, 0) / vals.length,
      };
    };

    const leftElbow = getStats("left_elbow");
    const rightElbow = getStats("right_elbow");
    const leftKnee = getStats("left_knee");
    const rightKnee = getStats("right_knee");
    const leftHip = getStats("left_hip");
    const rightHip = getStats("right_hip");
    const leftSh = getStats("left_shoulder");
    const rightSh = getStats("right_shoulder");
    const torso = getStats("torso_lean");

    const useLeft = activeMode !== "unilateral_right";
    const useRight = activeMode !== "unilateral_left";

    // Depth / Bottom flexion rules
    if (rules.max_bottom_elbow_angle != null) {
      const bottoms = [useLeft ? leftElbow?.min : null, useRight ? rightElbow?.min : null].filter((v) => v != null);
      if (bottoms.length && Math.min(...bottoms) > rules.max_bottom_elbow_angle + 8) {
        cues.push("Lower deeper — bend elbows to 90°");
      }
    }

    if (rules.max_bottom_knee_angle != null) {
      const bottoms = [useLeft ? leftKnee?.min : null, useRight ? rightKnee?.min : null].filter((v) => v != null);
      if (bottoms.length && Math.min(...bottoms) > rules.max_bottom_knee_angle + 8) {
        cues.push("Squat deeper — aim for parallel");
      }
    }

    // Peak contraction / Lockout rules
    if (rules.max_peak_elbow_angle != null) {
      const peaks = [useLeft ? leftElbow?.min : null, useRight ? rightElbow?.min : null].filter((v) => v != null);
      if (peaks.length && Math.min(...peaks) > rules.max_peak_elbow_angle + 10) {
        cues.push("Curl higher for full peak contraction");
      }
    }

    if (rules.min_lockout_elbow_angle != null) {
      const tops = [useLeft ? leftElbow?.max : null, useRight ? rightElbow?.max : null].filter((v) => v != null);
      if (tops.length && Math.max(...tops) < rules.min_lockout_elbow_angle - 8) {
        cues.push("Extend arms fully at lockout");
      }
    }

    if (rules.min_lockout_knee_angle != null) {
      const tops = [useLeft ? leftKnee?.max : null, useRight ? rightKnee?.max : null].filter((v) => v != null);
      if (tops.length && Math.max(...tops) < rules.min_lockout_knee_angle - 8) {
        cues.push("Extend knees fully at the top");
      }
    }

    if (rules.min_lockout_hip_angle != null) {
      const tops = [useLeft ? leftHip?.max : null, useRight ? rightHip?.max : null].filter((v) => v != null);
      if (tops.length && Math.max(...tops) < rules.min_lockout_hip_angle - 8) {
        cues.push("Squeeze glutes and lock hips out at top");
      }
    }

    if (rules.min_peak_shoulder_angle != null) {
      const peaks = [useLeft ? leftSh?.max : null, useRight ? rightSh?.max : null].filter((v) => v != null);
      if (peaks.length && Math.max(...peaks) < rules.min_peak_shoulder_angle - 8) {
        cues.push("Raise arms closer to shoulder height");
      }
    }

    if (rules.min_bottom_knee_angle != null) {
      const bottoms = [useLeft ? leftKnee?.min : null, useRight ? rightKnee?.min : null].filter((v) => v != null);
      if (bottoms.length && Math.min(...bottoms) < rules.min_bottom_knee_angle - 10) {
        cues.push("Keep knees softer — hinge hips back more");
      }
    }

    // Torso lean & isometric alignment rules
    if (torso) {
      if (rules.max_torso_lean != null && torso.max > rules.max_torso_lean + 7) {
        cues.push("Keep chest up — avoid excessive torso lean");
      }
      if (rules.min_torso_lean != null && torso.avg < rules.min_torso_lean - 8) {
        cues.push("Check body/bench incline angle");
      }
    }

    if (rules.min_hip_angle != null) {
      const hips = [leftHip?.min, rightHip?.min].filter((v) => v != null);
      if (hips.length && Math.min(...hips) < rules.min_hip_angle) {
        // Distinguish hip sag vs. hip pike using 2D normalized Y coordinates
        const lastFrame = frameBuffer[frameBuffer.length - 1];
        const norm = lastFrame?.normLandmarks;
        if (norm && norm[11] && norm[23] && norm[27]) {
          const lineY = (norm[11].y + norm[27].y) * 0.5;
          if (norm[23].y > lineY + 0.03) {
            cues.push("Hips dropping — brace core and squeeze glutes");
          } else {
            cues.push("Lower your hips — keep a straight line");
          }
        } else {
          cues.push("Brace core — keep hips in a straight line");
        }
      }
    }

    if (rules.min_knee_angle != null) {
      const knees = [leftKnee?.min, rightKnee?.min].filter((v) => v != null);
      if (knees.length && Math.min(...knees) < rules.min_knee_angle) {
        cues.push("Keep legs straight — lock knees out");
      }
    }

    return cues;
  }

  class LiveDTWScorer {
    constructor(baseUrl = DEFAULT_BASE_URL) {
      this.baseUrl = baseUrl;
      this.templateData = null;
      this.activeView = null;
      this.frameBuffer = [];
      this.lastRepScore = null;
      this.lastCues = [];
      this.lastMode = "bilateral";
      this.repHistory = [];

      // Isometric hold tracking (e.g., Plank)
      this.holdSeconds = 0;
      this.lastFrameTs = null;
      this.lastIsoEvalTs = 0;
    }

    async loadExercise(slug) {
      this.reset();
      if (!slug) {
        this.templateData = null;
        return null;
      }
      try {
        const res = await fetch(`${this.baseUrl}/${slug}.json`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        this.templateData = await res.json();
        this.activeView = this.templateData.templates?.[0]?.view || null;
        return this.templateData;
      } catch (err) {
        console.warn(`Could not load gold_forms/${slug}.json:`, err);
        this.templateData = null;
        return null;
      }
    }

    reset() {
      this.frameBuffer = [];
      this.lastRepScore = null;
      this.lastCues = [];
      this.lastMode = "bilateral";
      this.repHistory = [];
      this.holdSeconds = 0;
      this.lastFrameTs = null;
      this.lastIsoEvalTs = 0;
    }

    isIsometric() {
      return this.templateData?.mode === "isometric";
    }

    pushFrame(angles, normLandmarks = null) {
      if (!angles || !this.templateData) return null;

      const now = performance.now();
      const dt = this.lastFrameTs ? Math.min(0.25, (now - this.lastFrameTs) / 1000) : 0;
      this.lastFrameTs = now;

      this.frameBuffer.push({ angles, normLandmarks, ts: now });
      if (this.frameBuffer.length > 180) {
        this.frameBuffer.shift();
      }

      // Isometric sliding-window evaluation (Plank)
      if (this.isIsometric()) {
        if (this.frameBuffer.length >= 15 && now - this.lastIsoEvalTs >= 400) {
          this.lastIsoEvalTs = now;
          const windowSlice = this.frameBuffer.slice(-45);
          const result = this._scoreWindow(windowSlice);
          if (result) {
            this.lastRepScore = result.score;
            this.lastCues = result.cues;
            this.activeView = result.view;
          }
        }

        // Accumulate valid hold time when form score >= 75 and no active hip-sag/pike cue
        if (this.lastRepScore !== null && this.lastRepScore >= 75 && this.lastCues.length === 0) {
          this.holdSeconds += dt;
        }

        return {
          mode: "isometric",
          score: this.lastRepScore,
          cues: this.lastCues,
          holdSeconds: Number(this.holdSeconds.toFixed(1)),
          view: this.activeView,
        };
      }

      return null;
    }

    // Called by DynamicRepCounter whenever a repetition completes
    scoreCompletedRep() {
      if (!this.templateData || this.isIsometric() || this.frameBuffer.length < 8) {
        this.frameBuffer = [];
        return null;
      }

      const result = this._scoreWindow(this.frameBuffer);
      this.frameBuffer = []; // Reset buffer for the next rep

      if (result) {
        this.lastRepScore = result.score;
        this.lastCues = result.cues;
        this.lastMode = result.executionMode;
        this.activeView = result.view;
        this.repHistory.push(result);
      }
      return result;
    }

    _scoreWindow(buffer) {
      const templates = this.templateData.templates || [];
      if (!templates.length) return null;

      const baseWeights = { ...(this.templateData.weights || {}) };
      const primary = this.templateData.primary_joint || "left_elbow";

      // Auto-detect Bilateral vs. Alternating Unilateral execution from ROM
      let executionMode = "bilateral";
      if (primary.startsWith("left_")) {
        const rightPrimary = primary.replace("left_", "right_");
        const leftRom = rangeOf(extractValidSeries(buffer, primary));
        const rightRom = rangeOf(extractValidSeries(buffer, rightPrimary));
        const MIN_ACTIVE_ROM = 30;

        if (leftRom >= MIN_ACTIVE_ROM && rightRom < MIN_ACTIVE_ROM * 0.55) {
          executionMode = "unilateral_left";
        } else if (rightRom >= MIN_ACTIVE_ROM && leftRom < MIN_ACTIVE_ROM * 0.55) {
          executionMode = "unilateral_right";
        }
      }

      // Adjust weights dynamically so resting limbs or occluded far-side limbs never penalize score
      const activeWeights = {};
      for (const [joint, w] of Object.entries(baseWeights)) {
        if (executionMode === "unilateral_left") {
          if (joint.startsWith("right_") || joint.endsWith("_symmetry")) continue;
        } else if (executionMode === "unilateral_right") {
          if (joint.startsWith("left_") || joint.endsWith("_symmetry")) continue;
        }
        activeWeights[joint] = w;
      }

      // Evaluate across all available views (45_degree, side, front) and pick best-aligned view
      let bestMatch = null;
      for (const tpl of templates) {
        let weightedErrorSum = 0;
        let weightSum = 0;

        for (const [joint, weight] of Object.entries(activeWeights)) {
          if (!weight || weight <= 0) continue;
          const refCurve = tpl.reference_angles?.[joint];
          if (!refCurve || !refCurve.length) continue;

          const liveVals = extractValidSeries(buffer, joint);
          // Skip occluded joints (visibility < 0.7 in biomechanics.js)
          if (liveVals.length < 5) continue;

          const resampledLive = resampleCurve(liveVals, refCurve.length);
          const dist = dtwDistance1D(resampledLive, refCurve, 0.25);

          weightedErrorSum += dist * weight;
          weightSum += weight;
        }

        if (weightSum > 0) {
          const meanWeightedError = weightedErrorSum / weightSum;
          if (!bestMatch || meanWeightedError < bestMatch.meanWeightedError) {
            bestMatch = { view: tpl.view, meanWeightedError };
          }
        }
      }

      if (!bestMatch) return null;

      // Convert mean degree DTW error to intuitive 0-100 Form Score
      // <= 6° error -> ~100%, 15° error -> ~82%, 35°+ error -> <40%
      const effectiveError = Math.max(0, bestMatch.meanWeightedError - 5.0);
      const rawScore = 100 - effectiveError * 2.1;
      const score = Math.max(0, Math.min(100, Math.round(rawScore)));

      const cues = evaluateRules(buffer, this.templateData.rules, executionMode);

      return {
        score,
        cues,
        view: bestMatch.view,
        executionMode,
        meanErrorDeg: Number(bestMatch.meanWeightedError.toFixed(1)),
      };
    }
  }

  return { LiveDTWScorer };
})();
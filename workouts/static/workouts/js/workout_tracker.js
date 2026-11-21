// workouts/static/workouts/js/workout_tracker.js
(function () {
  const videoElement = document.getElementById("webcam");
  const canvasElement = document.getElementById("output_canvas");
  let encodeCanvas = null;
  const startBtn = document.getElementById("startCamBtn");
  const readySetBtn = document.getElementById("readySetBtn");
  const stopSendBtn = document.getElementById("stopSendBtn");
  const exerciseSelector = document.getElementById("exerciseSelector");
  const recordingStatus = document.getElementById("recordingStatus");
  const guideText = document.getElementById("guideText");
  const coachMode = document.getElementById("coachMode");
  const angleDisplay = document.getElementById("angleDisplay");
  const formScoreDisplay = document.getElementById("formScoreDisplay");
  const formCueDisplay = document.getElementById("formCueDisplay");
  const repLabelDisplay = document.getElementById("repLabelDisplay");

  let cameraStream = null;
  let websocket = null;
  let mediaRecorder = null;
  let recordedChunks = [];
  let frameLoopId = null;
  let audioCtx = null;
  let nextAudioStartTime = 0;
  let mpPose = null;
  let mpCamera = null;
  let repCounter = null;
  let dtwScorer = window.DTWEngine ? new window.DTWEngine.LiveDTWScorer() : null;
  let isSetStarted = false;

  // ==========================================
  // 🔐 PRODUCTION TOKEN HANDSHAKE ENGINE
  // ==========================================
  let memoryAccessToken = null;

  function isTokenExpired(token) {
    try {
      const base64Url = token.split(".")[1];
      const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split("")
          .map(function (c) {
            return "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2);
          })
          .join("")
      );
      const payload = JSON.parse(jsonPayload);
      return payload.exp * 1000 < Date.now() + 10000;
    } catch (e) {
      return true;
    }
  }

  async function getValidToken() {
    let token = memoryAccessToken || sessionStorage.getItem("accessToken");
    if (token && !isTokenExpired(token)) {
      memoryAccessToken = token;
      return token;
    }

    try {
      const refreshResponse = await fetch("/api/auth/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
      });

      if (refreshResponse.ok) {
        const data = await refreshResponse.json();
        memoryAccessToken = data.access;
        sessionStorage.setItem("accessToken", data.access);
        return data.access;
      } else {
        throw new Error("Refresh token expired");
      }
    } catch (err) {
      console.warn("Silent refresh failed, redirecting to login...");
      sessionStorage.removeItem("accessToken");
      window.location.href = "/auth/login/";
      return null;
    }
  }

  const POSE_CONNECTIONS = [
    [0, 1], [1, 2], [2, 3], [3, 7], [0, 4], [4, 5], [5, 6], [6, 8],
    [9, 10], [11, 12], [11, 13], [13, 15], [15, 17], [15, 19], [15, 21],
    [17, 19], [12, 14], [14, 16], [16, 18], [16, 20], [16, 22], [18, 20],
    [11, 23], [12, 24], [23, 24], [23, 25], [24, 26], [25, 27], [26, 28],
    [27, 29], [28, 30], [29, 31], [30, 32],
  ];

  function updateFormUI(score, cues) {
    if (formScoreDisplay) {
      if (score == null) {
        formScoreDisplay.textContent = "--%";
        formScoreDisplay.className = "text-2xl font-bold text-slate-400";
      } else {
        formScoreDisplay.textContent = `${score}%`;
        if (score >= 85) {
          formScoreDisplay.className = "text-2xl font-bold text-emerald-400";
        } else if (score >= 65) {
          formScoreDisplay.className = "text-2xl font-bold text-amber-400";
        } else {
          formScoreDisplay.className = "text-2xl font-bold text-rose-400";
        }
      }
    }

    if (formCueDisplay) {
      if (cues && cues.length > 0) {
        formCueDisplay.textContent = `⚠️ ${cues[0]}`;
        formCueDisplay.className = "text-sm font-medium text-amber-300";
      } else if (score != null) {
        formCueDisplay.textContent = "✅ Solid form!";
        formCueDisplay.className = "text-sm font-medium text-emerald-300";
      } else {
        formCueDisplay.textContent = "Complete a rep for DTW score";
        formCueDisplay.className = "text-sm text-slate-400";
      }
    }
  }

  /**
   * DynamicRepCounter
   * Tracks bilateral or alternating unilateral reps without double-counting,
   * and triggers DTW scoring upon each completed repetition.
   */
  class DynamicRepCounter {
    constructor({
      anchor_joint = 24,
      track_horizontally = false,
      fallback_anchor_joint = null,
      smoothingWindow = 5,
      visibilityThreshold = 0.6,
      minAmplitude = 0.025,
      onRepComplete = null,
    }) {
      this.anchorJoint = anchor_joint;
      this.fallbackAnchor = fallback_anchor_joint;
      this.trackHorizontally = Boolean(track_horizontally);
      this.onRepComplete = onRepComplete;

      this.smoothingWindow = smoothingWindow;
      this.visibilityThreshold = visibilityThreshold;
      this.minAmplitude = minAmplitude;

      // Mirror pairs (right <-> left) for bilateral / alternating support
      this.mirrorMap = {
        16: 15, 15: 16, // wrists
        14: 13, 13: 14, // elbows
        12: 11, 11: 12, // shoulders
        24: 23, 23: 24, // hips
        26: 25, 25: 26, // knees
        28: 27, 27: 28, // ankles
      };

      this.reset();
    }

    _makeTrackState(jointIdx) {
      return {
        jointIdx,
        buffer: [],
        rollingWindow: [],
        lastThreshold: "neutral",
        lastRepTs: 0,
      };
    }

    _smooth(state, value) {
      state.buffer.push(value);
      if (state.buffer.length > this.smoothingWindow) state.buffer.shift();
      return state.buffer.reduce((s, v) => s + v, 0) / state.buffer.length;
    }

    _stepJoint(state, landmarks, now) {
      const joint = landmarks[state.jointIdx];
      if (!joint || (joint.visibility != null && joint.visibility < this.visibilityThreshold)) {
        return false;
      }

      const axisValue = this.trackHorizontally ? joint.x : joint.y;
      const smoothed = this._smooth(state, axisValue);

      state.rollingWindow.push(smoothed);
      if (state.rollingWindow.length > 150) state.rollingWindow.shift();
      if (state.rollingWindow.length < 15) return false;

      const minVal = Math.min(...state.rollingWindow);
      const maxVal = Math.max(...state.rollingWindow);
      const range = maxVal - minVal;

      if (range > this.minAmplitude) {
        const normalized = (smoothed - minVal) / range;
        if (normalized < 0.2) {
          if (state.lastThreshold === "high" && now - state.lastRepTs > 550) {
            state.lastThreshold = "low";
            state.lastRepTs = now;
            return true;
          }
          state.lastThreshold = "low";
        } else if (normalized > 0.8) {
          state.lastThreshold = "high";
        }
      }
      return false;
    }

    update(landmarks) {
      if (!isSetStarted || !landmarks || !Array.isArray(landmarks)) return;
      this.framesSeen += 1;
      const now = performance.now();

      // Primary & mirror joint tracking (supports simultaneous bilateral & alternating curls/raises)
      const primaryDone = this._stepJoint(this.primaryState, landmarks, now);
      const mirrorDone = this.mirrorState ? this._stepJoint(this.mirrorState, landmarks, now) : false;

      // Update activeJoint highlight to whichever visible joint is active
      const pJoint = landmarks[this.anchorJoint];
      if (pJoint && (pJoint.visibility ?? 1) >= this.visibilityThreshold) {
        this.activeJoint = this.anchorJoint;
      } else if (this.mirrorState) {
        const mJoint = landmarks[this.mirrorState.jointIdx];
        if (mJoint && (mJoint.visibility ?? 1) >= this.visibilityThreshold) {
          this.activeJoint = this.mirrorState.jointIdx;
        }
      } else if (this.fallbackAnchor != null) {
        this.activeJoint = this.fallbackAnchor;
      }

      if (primaryDone || mirrorDone) {
        // Merge simultaneous bilateral completion within 450ms into 1 rep
        if (now - this.lastGlobalRepTs > 450) {
          this.repCount += 1;
          this.lastGlobalRepTs = now;
          if (typeof this.onRepComplete === "function") {
            this.onRepComplete(this.repCount);
          }
        }
      }
    }

    getRepCount() {
      return this.repCount;
    }

    reset() {
      this.repCount = 0;
      this.activeJoint = this.anchorJoint;
      this.framesSeen = 0;
      this.lastGlobalRepTs = 0;
      this.primaryState = this._makeTrackState(this.anchorJoint);
      const mirrorIdx = this.mirrorMap[this.anchorJoint];
      this.mirrorState = mirrorIdx != null ? this._makeTrackState(mirrorIdx) : null;
    }
  }

  function createAudioContext() {
    if (audioCtx && audioCtx.state !== "closed") return;
    audioCtx = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: 24000,
    });
    nextAudioStartTime = audioCtx.currentTime;
  }

  async function unlockAudio() {
    if (!audioCtx) createAudioContext();
    if (!audioCtx) return;
    if (audioCtx.state === "suspended") {
      await audioCtx.resume().catch(() => {});
    }
    const oscillator = audioCtx.createOscillator();
    oscillator.connect(audioCtx.destination);
    oscillator.start();
    oscillator.stop(audioCtx.currentTime + 0.01);
    nextAudioStartTime = audioCtx.currentTime;
  }

  function playAudioChunk(base64Data) {
    if (!audioCtx) return;
    if (audioCtx.state === "suspended") {
      audioCtx.resume().catch(() => {});
    }

    try {
      const binaryString = window.atob(base64Data);
      const sampleCount = binaryString.length / 2;
      const int16Array = new Int16Array(sampleCount);

      for (let i = 0; i < binaryString.length; i += 2) {
        int16Array[i / 2] =
          (binaryString.charCodeAt(i + 1) << 8) | binaryString.charCodeAt(i);
      }

      const float32Data = new Float32Array(sampleCount);
      for (let i = 0; i < sampleCount; i += 1) {
        float32Data[i] = int16Array[i] / 32768.0;
      }

      const audioBuffer = audioCtx.createBuffer(1, sampleCount, 24000);
      audioBuffer.getChannelData(0).set(float32Data);

      const source = audioCtx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioCtx.destination);

      const currentTime = audioCtx.currentTime;
      if (nextAudioStartTime < currentTime) {
        nextAudioStartTime = currentTime;
      }

      source.start(nextAudioStartTime);
      nextAudioStartTime += audioBuffer.duration;
    } catch (error) {
      console.error("Audio chunk decode failed", error);
    }
  }

  function teardownMedia() {
    isSetStarted = false;
    if (frameLoopId !== null) {
      clearInterval(frameLoopId);
      frameLoopId = null;
    }

    if (cameraStream) {
      cameraStream.getTracks().forEach((track) => track.stop());
      cameraStream = null;
    }

    if (websocket) {
      websocket.close();
      websocket = null;
    }

    try {
      if (mpCamera && typeof mpCamera.stop === "function") mpCamera.stop();
      mpCamera = null;
    } catch (e) {
      console.warn("Error stopping MediaPipe camera/pose", e);
    }

    videoElement.srcObject = null;
    videoElement.classList.add("hidden");
    recordingStatus.classList.add("hidden");
    readySetBtn.classList.add("hidden");
    stopSendBtn.classList.add("hidden");
    startBtn.classList.remove("hidden");
    guideText.textContent = "Press Start to connect to Live Coach.";
    coachMode.textContent = "Idle";

    try {
      document.getElementById("repDisplay").textContent = "0";
      document.getElementById("activeJointDisplay").textContent = "Joint: -";
      updateFormUI(null, []);
    } catch (e) {
      // noop
    }
  }

  function buildWebSocket() {
    const storedLang = localStorage.getItem("vertex_fit_lang") || "English";
    const websocketLanguageCode = storedLang === "Arabic" ? "ar" : "en";
    const wsScheme = window.location.protocol === "https:" ? "wss://" : "ws://";
    websocket = new WebSocket(`${wsScheme}${window.location.host}/ws/live-coaching/`);

    websocket.onopen = () => {
      recordingStatus.classList.remove("hidden");
      guideText.textContent = "Connecting to Coach...";
      coachMode.textContent = "Connecting";

      websocket.send(
        JSON.stringify({
          type: "session_init",
          exercise_name: exerciseSelector.options[exerciseSelector.selectedIndex].text,
          language: websocketLanguageCode,
        })
      );
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "setup_complete") {
          readySetBtn.classList.remove("hidden");
          guideText.textContent = "Phase 1 setup complete. Press Start Set when ready.";
          coachMode.textContent = "Ready";
          return;
        }

        if (data.type === "init_status") {
          readySetBtn.classList.remove("hidden");
          guideText.textContent = data.msg || "Live coach connected.";
          coachMode.textContent = "Ready";
          return;
        }

        if (data.type === "audio_chunk" && data.payload) {
          playAudioChunk(data.payload);
          return;
        }

        if (data.type === "coach_text" && data.text) {
          guideText.textContent = data.text;
          return;
        }

        if (data.type === "ready_ack") {
          guideText.textContent = "Coach is live. Sending frames now.";
          coachMode.textContent = "Live";
          startFrameStream();
          return;
        }

        if (data.type === "error") {
          console.error("Live coach error:", data.message);
          guideText.textContent = data.message || "Live coach error occurred.";
        }
      } catch (err) {
        console.warn("Invalid websocket payload", err);
      }
    };

    websocket.onerror = (event) => {
      console.error("WebSocket error", event);
      teardownMedia();
    };

    websocket.onclose = () => {
      teardownMedia();
    };
  }

  function startFrameStream() {
    if (!websocket || websocket.readyState !== WebSocket.OPEN) return;
    if (frameLoopId !== null) {
      clearInterval(frameLoopId);
      frameLoopId = null;
    }

    frameLoopId = setInterval(() => {
      if (videoElement.readyState < 2) return;

      if (!encodeCanvas) {
        encodeCanvas = document.createElement("canvas");
        encodeCanvas.width = 480;
        encodeCanvas.height = 360;
      }

      const ctx = encodeCanvas.getContext("2d");
      ctx.drawImage(videoElement, 0, 0, 480, 360);
      const dataUrl = encodeCanvas.toDataURL("image/jpeg", 0.6);
      const rawBase64 = dataUrl.split(",")[1];

      if (rawBase64.length < 100) return;

      websocket.send(
        JSON.stringify({
          type: "realtime_frame",
          frame: rawBase64,
          rep_count: repCounter ? repCounter.getRepCount() : 0,
          form_score: dtwScorer ? dtwScorer.lastRepScore : null,
          form_cues: dtwScorer ? dtwScorer.lastCues : [],
          hold_seconds: dtwScorer && dtwScorer.isIsometric() ? Number(dtwScorer.holdSeconds.toFixed(1)) : null,
        })
      );
    }, 500);
  }

  startBtn.addEventListener("click", async () => {
    startBtn.classList.add("hidden");
    stopSendBtn.classList.remove("hidden");

    try {
      createAudioContext();
      await unlockAudio();

      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { width: 480, height: 360, facingMode: "user" },
        audio: false,
      });

      videoElement.srcObject = cameraStream;
      videoElement.classList.remove("hidden");
      await videoElement.play();

      try {
        mediaRecorder = new MediaRecorder(cameraStream, { mimeType: "video/webm" });
        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) recordedChunks.push(event.data);
        };
        mediaRecorder.onstop = async () => {
          const videoBlob = new Blob(recordedChunks, { type: "video/webm" });
          recordedChunks = [];
          await uploadVideoForAnalysis(videoBlob);
        };
      } catch (err) {
        console.error("Failed to initialize MediaRecorder:", err);
      }

      // Load matching DTW Gold Form JSON template for the selected exercise
      const selected = exerciseSelector.options[exerciseSelector.selectedIndex];
      const slug = selected.dataset.slug || "";
      if (dtwScorer) {
        await dtwScorer.loadExercise(slug);
        if (repLabelDisplay) {
          repLabelDisplay.textContent = dtwScorer.isIsometric() ? "Hold Time (s)" : "Counted Reps";
        }
      }

      repCounter = new DynamicRepCounter({
        anchor_joint: selected.dataset.anchorJoint ? parseInt(selected.dataset.anchorJoint, 10) : 24,
        track_horizontally: selected.dataset.trackHorizontally === "true",
        fallback_anchor_joint: selected.dataset.fallbackAnchor
          ? parseInt(selected.dataset.fallbackAnchor, 10)
          : null,
        onRepComplete: () => {
          if (dtwScorer && !dtwScorer.isIsometric()) {
            const evalResult = dtwScorer.scoreCompletedRep();
            if (evalResult) {
              updateFormUI(evalResult.score, evalResult.cues);
            }
          }
        },
      });

      if (!mpPose) {
        mpPose = new Pose({
          locateFile: (file) =>
            `https://cdn.jsdelivr.net/npm/@mediapipe/pose@0.5.1675469404/${file}`,
        });

        mpPose.setOptions({
          modelComplexity: 1,
          smoothLandmarks: true,
          enableSegmentation: false,
          minDetectionConfidence: 0.5,
          minTrackingConfidence: 0.5,
        });
      }

      mpPose.onResults((results) => {
        try {
          if (results && results.poseLandmarks) {
            const isIso = dtwScorer && dtwScorer.isIsometric();

            // Dynamic exercises count reps; Isometric exercises (Plank) track hold time
            if (!isIso) {
              window.processPoseLandmarks(results.poseLandmarks);
            }

            // Extract 14 scale-invariant 3D angles (passing 2D landmarks for true visibility gating)
            let currentAngles = null;
            if (results.poseWorldLandmarks && window.Biomechanics) {
              currentAngles = window.Biomechanics.extractAllAngles(
                results.poseWorldLandmarks,
                results.poseLandmarks
              );

              if (isSetStarted && dtwScorer && currentAngles) {
                const isoUpdate = dtwScorer.pushFrame(currentAngles, results.poseLandmarks);
                if (isoUpdate) {
                  updateFormUI(isoUpdate.score, isoUpdate.cues);
                  const repEl = document.getElementById("repDisplay");
                  if (repEl) repEl.textContent = `${isoUpdate.holdSeconds}s`;
                }
              }
            }

            // Update Rep / Hold and Primary Joint Angle UI
            const repEl = document.getElementById("repDisplay");
            const jointEl = document.getElementById("activeJointDisplay");
            if (!isIso && repEl) {
              repEl.textContent = repCounter ? repCounter.getRepCount() : 0;
            }

            const active = repCounter && repCounter.activeJoint ? repCounter.activeJoint : "-";
            if (jointEl) {
              const viewTag = dtwScorer?.activeView ? ` (${dtwScorer.activeView})` : "";
              jointEl.textContent = `Joint: ${active}${viewTag}`;
            }

            if (angleDisplay && currentAngles && dtwScorer?.templateData?.primary_joint) {
              const pKey = dtwScorer.templateData.primary_joint;
              const pVal = currentAngles[pKey];
              angleDisplay.textContent = pVal != null ? `${Math.round(pVal)}°` : "--°";
            }

            // Draw skeleton overlay
            const ctx = canvasElement.getContext("2d");
            const cw = (canvasElement.width = videoElement.videoWidth || 480);
            const ch = (canvasElement.height = videoElement.videoHeight || 360);
            ctx.clearRect(0, 0, cw, ch);

            ctx.lineWidth = 2;
            ctx.strokeStyle = "rgba(0,200,0,0.7)";
            for (let i = 0; i < POSE_CONNECTIONS.length; i++) {
              const [a, b] = POSE_CONNECTIONS[i];
              const lmA = results.poseLandmarks[a];
              const lmB = results.poseLandmarks[b];
              if (lmA && lmB && (lmA.visibility ?? 1) >= 0.5 && (lmB.visibility ?? 1) >= 0.5) {
                ctx.beginPath();
                ctx.moveTo(lmA.x * cw, lmA.y * ch);
                ctx.lineTo(lmB.x * cw, lmB.y * ch);
                ctx.stroke();
              }
            }

            const idx = repCounter ? repCounter.activeJoint : null;
            if (idx != null && results.poseLandmarks[idx]) {
              const lm = results.poseLandmarks[idx];
              const x = lm.x * cw;
              const y = lm.y * ch;
              ctx.beginPath();
              ctx.arc(x, y, Math.max(6, cw * 0.015), 0, 2 * Math.PI);
              ctx.fillStyle = "rgba(255,0,0,0.85)";
              ctx.fill();
              ctx.lineWidth = 2;
              ctx.strokeStyle = "rgba(255,255,255,0.95)";
              ctx.stroke();
            }
          }
        } catch (e) {
          console.error("MediaPipe onResults error", e);
        }
      });

      mpCamera = new Camera(videoElement, {
        onFrame: async () => {
          if (mpPose && videoElement.readyState >= 2) {
            await mpPose.send({ image: videoElement });
          }
        },
        width: 480,
        height: 360,
      });

      mpCamera.start();
      buildWebSocket();
    } catch (error) {
      console.error("Camera startup failed", error);
      teardownMedia();
    }
  });

  readySetBtn.addEventListener("click", () => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      if (repCounter) repCounter.reset();
      if (dtwScorer) dtwScorer.reset();
      updateFormUI(null, []);
      isSetStarted = true;

      if (mediaRecorder && mediaRecorder.state === "inactive") {
        mediaRecorder.start();
      }

      websocket.send(JSON.stringify({ type: "user_ready", message: "جاهز" }));
      readySetBtn.classList.add("hidden");
      guideText.textContent = "Waiting for coach acknowledgement...";
      coachMode.textContent = "Starting";
    }
  });

  stopSendBtn.addEventListener("click", () => {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    teardownMedia();
    guideText.textContent = "Uploading video for deep AI analysis...";
    coachMode.textContent = "Analyzing";
  });

  window.processPoseLandmarks = function (landmarks) {
    try {
      if (repCounter && landmarks) repCounter.update(landmarks);
    } catch (err) {
      console.error("Rep counter update error", err);
    }
  };

  window.getRepCount = function () {
    return repCounter ? repCounter.getRepCount() : 0;
  };

  window.getActiveJoint = function () {
    return repCounter ? repCounter.activeJoint : null;
  };

  async function uploadVideoForAnalysis(videoBlob) {
    if (!videoBlob) return;

    guideText.textContent = "⏳ Preparing high-definition video chunk upload...";
    const exerciseId = exerciseSelector.value;
    const currentReps = repCounter ? repCounter.getRepCount() : 0;
    const preferredLanguage = localStorage.getItem("vertex_fit_lang") || "English";

    const formData = new FormData();
    formData.append("video", videoBlob, "workout_recording.webm");
    formData.append("exercise_id", exerciseId);
    formData.append("rep_count", currentReps);
    formData.append("language", preferredLanguage);

    try {
      const token = await getValidToken();
      const headers = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      } else {
        guideText.textContent = "❌ Auth token missing. Please log in again.";
        return;
      }

      const response = await fetch("/api/workouts/upload/", {
        method: "POST",
        body: formData,
        headers: headers,
      });

      const data = await response.json();

      if (response.ok) {
        const viewAnalysisBtn = document.getElementById("viewAnalysisBtn");
        guideText.textContent = "✅ Video uploaded successfully! Deep analysis running.";
        viewAnalysisBtn.setAttribute("href", `/api/workouts/session/${data.session_id}/analysis/`);
        viewAnalysisBtn.classList.remove("hidden");
        viewAnalysisBtn.classList.add("inline-flex");
      } else {
        guideText.textContent = `❌ Upload failed: ${data.error || "Unknown error"}`;
      }
    } catch (error) {
      console.error("Upload error:", error);
      guideText.textContent = "❌ Network error during upload.";
    }
  }
})();

window.addEventListener("beforeunload", () => {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.close();
  }
});
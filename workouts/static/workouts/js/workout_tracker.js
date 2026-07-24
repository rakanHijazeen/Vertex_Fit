(function () {
  const videoElement = document.getElementById("webcam");
  const canvasElement = document.getElementById("output_canvas"); // visible overlay for joints/tracers
  let encodeCanvas = null; // hidden canvas for clean JPEG frames (created at runtime)
  const startBtn = document.getElementById("startCamBtn");
  const readySetBtn = document.getElementById("readySetBtn");
  const stopSendBtn = document.getElementById("stopSendBtn");
  const exerciseSelector = document.getElementById("exerciseSelector");
  const recordingStatus = document.getElementById("recordingStatus");
  const guideText = document.getElementById("guideText");
  const coachMode = document.getElementById("coachMode");
  const angleDisplay = document.getElementById("angleDisplay");

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
  let isSetStarted = false;

  // ==========================================
  // 🔐 PRODUCTION TOKEN HANDSHAKE ENGINE
  // ==========================================
  let memoryAccessToken = null;

  function isTokenExpired(token) {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
      }).join(''));
      const payload = JSON.parse(jsonPayload);
      return payload.exp * 1000 < (Date.now() + 10000);
    } catch (e) {
      return true;
    }
  }

  async function getValidToken() {    
      if (memoryAccessToken && !isTokenExpired(memoryAccessToken)) {
      return memoryAccessToken;
    }

    try {
      const refreshResponse = await fetch("/api/auth/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: 'include'
      });

      if (refreshResponse.ok) {
        const data = await refreshResponse.json();
        memoryAccessToken = data.access; // Store the new access token only in memory
        return data.access;
      } else {
        throw new Error("Refresh token expired");
      }
    } catch (err) {
      console.warn("Silent refresh failed, redirecting to login...");
      window.location.href = "/auth/login/";
      return null;
    }
  }

  // Common MediaPipe Pose connections (pairs of landmark indices) used to draw skeletal tracer lines
  const POSE_CONNECTIONS = [
    [0, 1],
    [1, 2],
    [2, 3],
    [3, 7],
    [0, 4],
    [4, 5],
    [5, 6],
    [6, 8],
    [9, 10],
    [11, 12],
    [11, 13],
    [13, 15],
    [15, 17],
    [15, 19],
    [15, 21],
    [17, 19],
    [12, 14],
    [14, 16],
    [16, 18],
    [16, 20],
    [16, 22],
    [18, 20],
    [11, 23],
    [12, 24],
    [23, 24],
    [23, 25],
    [24, 26],
    [25, 27],
    [26, 28],
    [27, 29],
    [28, 30],
    [29, 31],
    [30, 32],
  ];

  /**
   * DynamicRepCounter
   * A zero-math (no hardcoded per-exercise trigonometry) state machine that
   * derives rep-counts from a single anchor joint (with optional fallback)
   * using smoothing, visibility checks, and axis-aware direction detection.
   *
   * Usage:
   *   const counter = new DynamicRepCounter({ anchor_joint: 16, track_horizontally: false, fallback_anchor_joint: 12 });
   *   // call `counter.update(landmarks)` on each MediaPipe frame
   *   // read `counter.getRepCount()` when sending to the server
   */
  class DynamicRepCounter {
    constructor({
      anchor_joint = 24,
      track_horizontally = false,
      fallback_anchor_joint = null,
      smoothingWindow = 5,
      visibilityThreshold = 0.6,
      minAmplitude = 0.02,
    }) {
      this.anchorJoint = anchor_joint;
      this.fallbackAnchor = fallback_anchor_joint;
      this.trackHorizontally = Boolean(track_horizontally);

      // smoothing & thresholds
      this.smoothingWindow = smoothingWindow;
      this.visibilityThreshold = visibilityThreshold;
      this.minAmplitude = minAmplitude; // normalized coordinate amplitude required to mark movement

      // runtime buffers/state
      this.buffer = [];
      this.rollingWindow = [];
      this.rollingWindowSize = 150; // ~5 seconds at 30fps
      this.repCount = 0;
      this.activeJoint = this.anchorJoint;
      this.lastTrackedJoint = this.anchorJoint;
      this.framesSeen = 0;

      // State machine variables
      this.lastThreshold = "neutral"; // "neutral", "low", "high"
    }

    // moving average smoothing
    _smooth(value) {
      this.buffer.push(value);
      if (this.buffer.length > this.smoothingWindow) this.buffer.shift();
      const sum = this.buffer.reduce((s, v) => s + v, 0);
      return sum / this.buffer.length;
    }

    // public API: update with MediaPipe `landmarks` array
    // landmarks are expected in the MediaPipe format: {x, y, visibility}
    update(landmarks) {
      if (!isSetStarted) return;
      this.framesSeen += 1;
      if (!landmarks || !Array.isArray(landmarks)) return;

      // Determine the active joint based on visibility and fallback
      let joint = landmarks[this.anchorJoint];
      let selectedJointIndex = this.anchorJoint;

      if (
        !joint ||
        (joint.visibility != null &&
          joint.visibility < this.visibilityThreshold)
      ) {
        if (this.fallbackAnchor != null) {
          const fallback = landmarks[this.fallbackAnchor];
          if (
            fallback &&
            fallback.visibility != null &&
            fallback.visibility >= this.visibilityThreshold
          ) {
            selectedJointIndex = this.fallbackAnchor;
            joint = fallback;
          }
        }
      }

      this.activeJoint = selectedJointIndex;

      // Reset state if we switched joints to prevent coordinate jumps
      if (this.activeJoint !== this.lastTrackedJoint) {
        this.buffer = [];
        this.rollingWindow = [];
        this.lastThreshold = "neutral";
        this.lastTrackedJoint = this.activeJoint;
      }

      if (!joint) return; // nothing to track

      const axisValue = this.trackHorizontally ? joint.x : joint.y;
      const smoothed = this._smooth(axisValue);

      this.rollingWindow.push(smoothed);
      if (this.rollingWindow.length > this.rollingWindowSize) {
        this.rollingWindow.shift();
      }

      // Wait until we have enough history to determine range
      if (this.rollingWindow.length < 15) {
        return;
      }

      const minVal = Math.min(...this.rollingWindow);
      const maxVal = Math.max(...this.rollingWindow);
      const range = maxVal - minVal;

      if (range > this.minAmplitude) {
        const normalized = (smoothed - minVal) / range;
        if (normalized < 0.2) {
          if (this.lastThreshold === "high") {
            this.repCount += 1;
          }
          this.lastThreshold = "low";
        } else if (normalized > 0.8) {
          this.lastThreshold = "high";
        }
      }
    }

    getRepCount() {
      return this.repCount;
    }

    reset() {
      this.buffer = [];
      this.rollingWindow = [];
      this.repCount = 0;
      this.activeJoint = this.anchorJoint;
      this.lastTrackedJoint = this.anchorJoint;
      this.framesSeen = 0;
      this.lastThreshold = "neutral";
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
    if (!audioCtx) {
      createAudioContext();
    }

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

    // stop MediaPipe camera loop if running
    try {
      if (mpCamera && typeof mpCamera.stop === "function") mpCamera.stop();
      mpCamera = null;
      if (mpPose && typeof mpPose.close === "function") mpPose.close();
      mpPose = null;
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
    // reset UI counters
    try {
      document.getElementById("repDisplay").textContent = "0";
      document.getElementById("activeJointDisplay").textContent = "Joint: -";
    } catch (e) {
      // noop
    }
  }

  function buildWebSocket() {
    // 1. Read the synchronized readable language from localStorage
    const storedLang = localStorage.getItem("vertex_fit_lang") || "English";

    // 2. Map it cleanly to the 'ar' or 'en' code strings your backend expects
    const websocketLanguageCode = storedLang === "Arabic" ? "ar" : "en";
    const wsScheme = window.location.protocol === "https:" ? "wss://" : "ws://";
    websocket = new WebSocket(
      `${wsScheme}${window.location.host}/ws/live-coaching/`,
    );

    websocket.onopen = () => {
      recordingStatus.classList.remove("hidden");
      guideText.textContent = "Connecting to Coach...";
      coachMode.textContent = "Connecting";

      websocket.send(
        JSON.stringify({
          type: "session_init",
          exercise_name:
            exerciseSelector.options[exerciseSelector.selectedIndex].text,
          language: websocketLanguageCode,
        }),
      );
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "setup_complete") {
          readySetBtn.classList.remove("hidden");
          guideText.textContent =
            "Phase 1 setup complete. Press ready when you are ready.";
          coachMode.textContent = "Ready";
          return;
        }

        if (data.type === "init_status") {
          console.log("Live coach ready:", data.msg);
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
      if (videoElement.readyState < 2) return; // Wait until metadata is loaded

      // Use a hidden encode canvas for clean JPEG frames (no overlay)
      if (!encodeCanvas) {
        encodeCanvas = document.createElement("canvas");
        encodeCanvas.width = 480;
        encodeCanvas.height = 360;
      }

      const ctx = encodeCanvas.getContext("2d");
      ctx.drawImage(videoElement, 0, 0, 480, 360);
      const dataUrl = encodeCanvas.toDataURL("image/jpeg", 0.6);
      const rawBase64 = dataUrl.split(",")[1];

      if (rawBase64.length < 100) {
        // Tiny strings are usually error headers, not images
        console.error("Canvas is empty!");
        return;
      }

      websocket.send(
        JSON.stringify({
          type: "realtime_frame",
          frame: rawBase64,
          rep_count: repCounter ? repCounter.getRepCount() : 0,
        }),
      );
    }, 500); // Send a frame every 500ms (2 FPS) to reduce bandwidth and processing load
  }

  startBtn.addEventListener("click", async () => {
    startBtn.classList.add("hidden");
    stopSendBtn.classList.remove("hidden");

    try {
      createAudioContext();
      await unlockAudio();
      console.log("🔊 Audio unlocked, state=", audioCtx.state);

      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { width: 480, height: 360, facingMode: "user" },
        audio: false,
      });

      videoElement.srcObject = cameraStream;
      videoElement.classList.remove("hidden");
      await videoElement.play();
      // Initialize MediaRecorder for video capture (optional, for upload)
      try {
        mediaRecorder = new MediaRecorder(cameraStream, {
          mimeType: "video/webm",
        });

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            recordedChunks.push(event.data);
          }
        };

        mediaRecorder.onstop = async () => {
          const videoBlob = new Blob(recordedChunks, { type: "video/webm" });
          recordedChunks = []; // Reset for next time

          // Trigger the upload and analysis flow
          await uploadVideoForAnalysis(videoBlob);
        };
      } catch (err) {
        console.error("Failed to initialize MediaRecorder:", err);
      }

      // Initialize the dynamic rep counter using dataset attributes on the selected option
      try {
        const selected =
          exerciseSelector.options[exerciseSelector.selectedIndex];
        const cfg = {
          anchor_joint: selected.dataset.anchorJoint
            ? parseInt(selected.dataset.anchorJoint, 10)
            : parseInt(selected.value, 10) || 24,
          track_horizontally: selected.dataset.trackHorizontally === "true",
          fallback_anchor_joint: selected.dataset.fallbackAnchor
            ? parseInt(selected.dataset.fallbackAnchor, 10)
            : null,
        };
        repCounter = new DynamicRepCounter(cfg);
      } catch (e) {
        // fallback to defaults if dataset isn't present
        repCounter = new DynamicRepCounter({
          anchor_joint: 24,
          track_horizontally: false,
          fallback_anchor_joint: null,
        });
      }

      // Initialize MediaPipe Pose and Camera wrapper to feed landmarks into the rep counter
      try {
        // Use global Pose and Camera from the included scripts
        mpPose = new Pose({
          locateFile: (file) =>
            `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
        });

        mpPose.setOptions({
          modelComplexity: 1,
          smoothLandmarks: true,
          enableSegmentation: false,
          minDetectionConfidence: 0.5,
          minTrackingConfidence: 0.5,
        });

        mpPose.onResults((results) => {
          try {
            if (results && results.poseLandmarks) {
              window.processPoseLandmarks(results.poseLandmarks);

              // Update UI counters and angle in real-time
              const rc = repCounter ? repCounter.getRepCount() : 0;
              const active =
                repCounter && repCounter.activeJoint
                  ? repCounter.activeJoint
                  : "-";
              const repEl = document.getElementById("repDisplay");
              const jointEl = document.getElementById("activeJointDisplay");
              if (repEl) repEl.textContent = rc;
              if (jointEl) jointEl.textContent = `Joint: ${active}`;

              // Calculate and display joint angle (e.g., angle at active joint using neighbors)
              try {
                const angle = computeJointAngle(results.poseLandmarks, active);
                if (angleDisplay) angleDisplay.textContent = angle + "°";
              } catch (e) {
                // noop
              }

              // Draw skeleton overlay on the visible canvas (not affecting frame encoding)
              try {
                const ctx = canvasElement.getContext("2d");
                const cw = (canvasElement.width =
                  videoElement.videoWidth || 480);
                const ch = (canvasElement.height =
                  videoElement.videoHeight || 360);

                // clear overlay canvas (video background is handled by CSS)
                ctx.clearRect(0, 0, cw, ch);

                // Draw skeletal tracer lines between connected landmarks
                try {
                  ctx.lineWidth = 2;
                  ctx.strokeStyle = "rgba(0,200,0,0.7)";
                  for (let i = 0; i < POSE_CONNECTIONS.length; i++) {
                    const [a, b] = POSE_CONNECTIONS[i];
                    const lmA = results.poseLandmarks[a];
                    const lmB = results.poseLandmarks[b];
                    if (
                      lmA &&
                      lmB &&
                      lmA.x != null &&
                      lmA.y != null &&
                      lmB.x != null &&
                      lmB.y != null
                    ) {
                      const ax = lmA.x * cw;
                      const ay = lmA.y * ch;
                      const bx = lmB.x * cw;
                      const by = lmB.y * ch;
                      ctx.beginPath();
                      ctx.moveTo(ax, ay);
                      ctx.lineTo(bx, by);
                      ctx.stroke();
                    }
                  }

                  // Highlight the active joint with a circle and label
                  const idx = repCounter ? repCounter.activeJoint : null;
                  if (idx != null) {
                    const lm = results.poseLandmarks[idx];
                    if (lm && lm.x != null && lm.y != null) {
                      const x = lm.x * cw;
                      const y = lm.y * ch;
                      ctx.beginPath();
                      ctx.arc(x, y, Math.max(6, cw * 0.015), 0, 2 * Math.PI);
                      ctx.fillStyle = "rgba(255,0,0,0.85)";
                      ctx.fill();
                      ctx.lineWidth = 2;
                      ctx.strokeStyle = "rgba(255,255,255,0.95)";
                      ctx.stroke();
                      ctx.font = "14px sans-serif";
                      ctx.fillStyle = "white";
                      ctx.fillText(`J${idx}`, x + 8, y - 8);
                    }
                  }
                } catch (sErr) {
                  console.warn("Tracer draw error", sErr);
                }
              } catch (drawErr) {
                console.warn("Overlay draw failed", drawErr);
              }
            }
          } catch (e) {
            console.error("MediaPipe onResults error", e);
          }
        });

        mpCamera = new Camera(videoElement, {
          onFrame: async () => {
            await mpPose.send({ image: videoElement });
          },
          width: 480,
          height: 360,
        });

        mpCamera.start();
      } catch (e) {
        console.warn("MediaPipe initialization failed", e);
      }

      buildWebSocket();
    } catch (error) {
      console.error("Camera startup failed", error);
      teardownMedia();
    }
  });

  readySetBtn.addEventListener("click", () => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      // and recalibrate its baseline when you are actually standing in position!
      if (repCounter) {
        repCounter.reset();
      }
      isSetStarted = true;
      // Start the MediaRecorder only when the user is ready, to avoid recording unnecessary footage
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
    // Stop the recording first before tearing down the media stream
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    teardownMedia();
    // Update UI to show a loading state while uploading
    guideText.textContent = "Uploading video for deep AI analysis...";
    coachMode.textContent = "Analyzing";
  });
  // Expose a helper for MediaPipe or other pose engines to push landmarks into the counter
  // Example usage from your MediaPipe callback: window.processPoseLandmarks(poseLandmarks);
  window.processPoseLandmarks = function (landmarks) {
    try {
      if (repCounter && landmarks) repCounter.update(landmarks);
    } catch (err) {
      console.error("Rep counter update error", err);
    }
  };

  // Expose lightweight getters for UI or external polling
  window.getRepCount = function () {
    return repCounter ? repCounter.getRepCount() : 0;
  };

  window.getActiveJoint = function () {
    return repCounter ? repCounter.activeJoint : null;
  };

  // Helper to compute the angle at a joint given two neighboring landmarks
  // For simplicity, we estimate angle as the angle of the vector from parent to child
  function computeJointAngle(landmarks, jointIdx) {
    if (
      jointIdx == null ||
      typeof jointIdx === "string" ||
      !landmarks ||
      landmarks.length === 0
    ) {
      return 0;
    }

    const idx = parseInt(jointIdx, 10);

    // Common parent-child relationships in MediaPipe Pose
    // For ankle (index 16), parent is knee (14); for knee (14), parent is hip (12)
    const parentMap = {
      16: 14,
      14: 12,
      15: 13,
      13: 11,
      12: 11,
      11: 23,
      24: 23,
      23: 26,
      26: 28,
      28: 32,
    };

    const parentIdx = parentMap[idx];
    if (parentIdx == null) return 0; // no parent, can't compute angle

    const child = landmarks[idx];
    const parent = landmarks[parentIdx];

    if (
      !child ||
      !parent ||
      child.x == null ||
      child.y == null ||
      parent.x == null ||
      parent.y == null
    ) {
      return 0;
    }

    // compute angle as arctangent of vertical/horizontal displacement
    const dx = child.x - parent.x;
    const dy = child.y - parent.y;
    const angle = Math.atan2(dy, dx) * (180 / Math.PI);
    return Math.round(Math.abs(angle));
  }

  async function uploadVideoForAnalysis(videoBlob) {
    if (!videoBlob) return;

    // 1. Update the sidebar guide text status
    guideText.textContent =
      "⏳ Preparing high-definition video chunk upload...";

    const exerciseId = exerciseSelector.value;
    const currentReps = repCounter ? repCounter.getRepCount() : 0;

    // Read from localStorage instead of the old DOM element ID
    const preferredLanguage =
      localStorage.getItem("vertex_fit_lang") || "English";

    const formData = new FormData();
    // 'video' matches request.data.get('video') in your view
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
        // Fetch automatically sets the correct multipart boundary when passing FormData
        body: formData,
        headers: headers,
      });

      const data = await response.json();

      if (response.ok) {
        // 1. Grab the button we added to tracker.html
        const viewAnalysisBtn = document.getElementById("viewAnalysisBtn");

        // 2. Update the sidebar guide text to reflect status
        guideText.textContent =
          "✅ Video uploaded successfully! Deep analysis running.";

        // 3. Assign the dynamic Django URL and unhide the dedicated UI button
        viewAnalysisBtn.setAttribute(
          "href",
          `/api/workouts/session/${data.session_id}/analysis/`,
        );
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
// Clean up on page unload
window.addEventListener("beforeunload", () => {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.close();
  }
});

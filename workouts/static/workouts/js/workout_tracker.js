(function () {
  const videoElement = document.getElementById("webcam");
  const canvasElement = document.getElementById("output_canvas");
  const canvasCtx = canvasElement.getContext("2d");
  const startBtn = document.getElementById("startCamBtn");
  const stopSendBtn = document.getElementById("stopSendBtn");
  const recordingStatus = document.getElementById("recordingStatus");
  const exerciseSelector = document.getElementById("exerciseSelector");

  const csrfToken = document
    .getElementById("django-context")
    .getAttribute("data-csrf");

  let wakeLock = null;
  let repCount = 0;
  let stage = "down";
  let lastCueTime = 0;
  const CUE_COOLDOWN = 2500;

  let mediaRecorder;
  let recordedChunks = [];
  let streamInstance;

  function speakJordanian(text) {
    const now = Date.now();
    if (now - lastCueTime < CUE_COOLDOWN) return;

    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "ar-JO";
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
      lastCueTime = now;
    }
  }

  async function requestWakeLock() {
    try {
      if ("wakeLock" in navigator) {
        wakeLock = await navigator.wakeLock.request("screen");
      }
    } catch (err) {
      console.warn(`Wake Lock Exception: ${err.message}`);
    }
  }

  function calculateAngle(p1, p2, p3) {
    let radians =
      Math.atan2(p3.y - p2.y, p3.x - p2.x) -
      Math.atan2(p1.y - p2.y, p1.x - p2.x);
    let angle = Math.abs((radians * 180.0) / Math.PI);
    if (angle > 180.0) angle = 360 - angle;
    return Math.round(angle);
  }

  function onResults(results) {
    if (!results.poseLandmarks) return;

    if (
      canvasElement.width !== canvasElement.clientWidth ||
      canvasElement.height !== canvasElement.clientHeight
    ) {
      canvasElement.width = canvasElement.clientWidth;
      canvasElement.height = canvasElement.clientHeight;
    }

    canvasCtx.save();
    canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
    canvasCtx.translate(canvasElement.width, 0);
    canvasCtx.scale(-1, 1);
    canvasCtx.drawImage(
      results.image,
      0,
      0,
      canvasElement.width,
      canvasElement.height,
    );
    canvasCtx.restore();

    const shoulder = results.poseLandmarks[11];
    const elbow = results.poseLandmarks[13];
    const wrist = results.poseLandmarks[15];

    if (shoulder && elbow && wrist) {
      const currentAngle = calculateAngle(shoulder, elbow, wrist);
      document.getElementById("angleDisplay").textContent = `${currentAngle}°`;

      if (currentAngle > 165) {
        if (stage === "up") speakJordanian("انزل كمان، ريح العضلة للاخر");
        stage = "down";
      }
      if (currentAngle < 45 && stage === "down") {
        stage = "up";
        repCount++;
        document.getElementById("repDisplay").textContent = repCount;

        if (repCount % 5 === 0) {
          speakJordanian(`وحش يا كابتن! هانت، ضايل شوي`);
        } else {
          speakJordanian(`${repCount}! كمل كمان`);
        }
      }
    }
  }

  const pose = new Pose({
    locateFile: (file) =>
      `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
  });
  pose.setOptions({
    modelComplexity: 1,
    smoothLandmarks: true,
    minDetectionConfidence: 0.5,
    minTrackingConfidence: 0.5,
  });
  pose.onResults(onResults);

  startBtn.addEventListener("click", async () => {
    startBtn.classList.add("hidden");
    stopSendBtn.classList.remove("hidden");
    recordingStatus.classList.remove("hidden");

    await requestWakeLock();
    speakJordanian("عاش يا وحش، بلش التمرين");

    streamInstance = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480, facingMode: "user" },
      audio: false,
    });

    videoElement.srcObject = streamInstance;
    recordedChunks = [];

    // 💡 Fix: Keep recording format consistent
    mediaRecorder = new MediaRecorder(streamInstance, {
      mimeType: "video/webm;codecs=vp8",
    });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) recordedChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      // Create a solid file block out of all collected chunks
      const videoBlob = new Blob(recordedChunks, { type: "video/mp4" });
      speakJordanian("جاري تحليل الجولة، ريح شوي");

      const formData = new FormData();
      formData.append("video", videoBlob, "workout_set.mp4");
      formData.append("exercise_id", exerciseSelector.value);
      formData.append("rep_count", repCount);

      try {
        recordingStatus.textContent = "🔄 Uploading video to cloud pipeline...";
        recordingStatus.className =
          "text-xs bg-amber-500/20 text-amber-400 border border-amber-500/30 px-3 py-1 rounded-full animate-pulse";

        const response = await fetch("/api/workouts/upload/", {
          method: "POST",
          body: formData,
          credentials: "include",
          headers: {
            "X-CSRFToken": csrfToken,
          },
        });

        if (response.ok) {
          recordingStatus.className =
            "text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-3 py-1 rounded-full font-bold";
          recordingStatus.textContent =
            "✅ Upload completed! VLM process queued.";
        } else {
          recordingStatus.textContent = "❌ Upload failed.";
        }
      } catch (error) {
        console.error("Payload network failure:", error);
        recordingStatus.textContent = "❌ Communication exception occurred.";
      }
    };

    const camera = new Camera(videoElement, {
      onFrame: async () => {
        await pose.send({ image: videoElement });
      },
      width: 640,
      height: 480,
    });
    camera.start();

    // 💡 FIX 1: Remove the (1000) interval timeslice requirement so it builds continuously!
    mediaRecorder.start();
  });

  stopSendBtn.addEventListener("click", () => {
    stopSendBtn.classList.add("hidden");

    // 💡 FIX 2: Stop the recorder FIRST so it completely finishes writing the buffer safely
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }

    // Shut down camera tracks completely after handoff
    if (streamInstance) {
      streamInstance.getTracks().forEach((track) => track.stop());
    }
  });
})();

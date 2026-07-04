(function () {
  const videoElement = document.getElementById("webcam");
  const canvasElement = document.getElementById("output_canvas");
  const startBtn = document.getElementById("startCamBtn");
  const readySetBtn = document.getElementById("readySetBtn");
  const stopSendBtn = document.getElementById("stopSendBtn");
  const exerciseSelector = document.getElementById("exerciseSelector");
  const recordingStatus = document.getElementById("recordingStatus");
  const guideText = document.getElementById("guideText");
  const coachMode = document.getElementById("coachMode");

  let cameraStream = null;
  let websocket = null;
  let frameLoopId = null;
  let audioCtx = null;
  let nextAudioStartTime = 0;

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

    videoElement.srcObject = null;
    videoElement.classList.add("hidden");
    recordingStatus.classList.add("hidden");
    readySetBtn.classList.add("hidden");
    stopSendBtn.classList.add("hidden");
    startBtn.classList.remove("hidden");
    guideText.textContent = "Press Start to connect to Live Coach.";
    coachMode.textContent = "Idle";
  }

  function buildWebSocket() {
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
          guideText.textContent = data.msg || "Live coach connected.";
          coachMode.textContent = "Waiting";
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

      const ctx = canvasElement.getContext("2d");
      canvasElement.width = 480;
      canvasElement.height = 360;
      ctx.drawImage(videoElement, 0, 0, 480, 360);
      const dataUrl = canvasElement.toDataURL("image/jpeg", 0.6);
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

      buildWebSocket();
    } catch (error) {
      console.error("Camera startup failed", error);
      teardownMedia();
    }
  });

  readySetBtn.addEventListener("click", () => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({ type: "user_ready", message: "جاهز" }));
      readySetBtn.classList.add("hidden");
      guideText.textContent = "Waiting for coach acknowledgement...";
      coachMode.textContent = "Starting";
    }
  });

  stopSendBtn.addEventListener("click", () => {
    teardownMedia();
  });
})();
// Clean up on page unload
window.addEventListener("beforeunload", () => {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.close();
  }
});

// workout_tracker.js
(function () {
  const videoElement = document.getElementById("webcam");
  const canvasElement = document.getElementById("output_canvas");
  const canvasCtx = canvasElement.getContext("2d");
  const startBtn = document.getElementById("startCamBtn");
  const stopSendBtn = document.getElementById("stopSendBtn");
  const exerciseSelector = document.getElementById("exerciseSelector");

  let vlmSocket = null;
  let streamInstance = null;
  let liveBroadcastTimer = null;
  let lastCueTime = 0;
  const CUE_COOLDOWN = 2000;

  function speakJordanian(text) {
    const now = Date.now();
    if (now - lastCueTime < CUE_COOLDOWN) return;

    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "ar-JO";
      utterance.rate = 1.1;
      window.speechSynthesis.speak(utterance);
      lastCueTime = now;
    }
  }

  function initializeLiveEngine() {
    const wsScheme = window.location.protocol === "https:" ? "wss://" : "ws://";
    vlmSocket = new WebSocket(
      `${wsScheme}${window.location.host}/ws/live-coaching/`,
    );

    vlmSocket.onopen = () => {
      console.log("🚀 Production Live Engine Handshake Activated.");
      vlmSocket.send(
        JSON.stringify({
          type: "session_init",
          exercise_name:
            exerciseSelector.options[exerciseSelector.selectedIndex].text,
        }),
      );

      // Start broadcasting continuous frames at 1 FPS safely matching Gemini Live spec
      startLiveBroadcasting();
    };

    vlmSocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.cue) {
        speakJordanian(data.cue);
      }
    };
  }

  function startLiveBroadcasting() {
    // 1 Frame Per Second matches production Gemini Multimodal Live API design specifications
    liveBroadcastTimer = setInterval(() => {
      if (!vlmSocket || vlmSocket.readyState !== WebSocket.OPEN) return;

      // Draw active webcam frame straight onto canvas context layer
      canvasCtx.drawImage(
        videoElement,
        0,
        0,
        canvasElement.width,
        canvasElement.height,
      );

      // Extract clean JPEG binary frame compression matching API layout requirements
      const dataUrl = canvasElement.toDataURL("image/jpeg", 0.7);
      const rawBase64 = dataUrl.split(",")[1]; // Extract pure string chunk away from header metadata

      vlmSocket.send(
        JSON.stringify({
          type: "realtime_frame",
          realtimeInput: {
            video: {
              data: rawBase64,
              mimeType: "image/jpeg",
            },
          },
        }),
      );
    }, 1000); // 1 FPS is the recommended maximum for video input
  }

  startBtn.addEventListener("click", async () => {
    startBtn.classList.add("hidden");
    stopSendBtn.classList.remove("hidden");

    canvasElement.width = 480;
    canvasElement.height = 360;

    streamInstance = await navigator.mediaDevices.getUserMedia({
      video: { width: 480, height: 360, facingMode: "user" },
      audio: false, // Turn on true if you want the backend proxy to handle audio/voice interactions too
    });

    videoElement.srcObject = streamInstance;
    videoElement.play();

    initializeLiveEngine();
  });

  stopSendBtn.addEventListener("click", () => {
    stopSendBtn.classList.add("hidden");
    startBtn.classList.remove("hidden");

    if (liveBroadcastTimer) clearInterval(liveBroadcastTimer);
    if (vlmSocket) vlmSocket.close();
    if (streamInstance) {
      streamInstance.getTracks().forEach((track) => track.stop());
    }
  });
})();

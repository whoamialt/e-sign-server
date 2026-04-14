// === State ===
let currentTab = "type";
let isDrawing = false;
let hasDrawn = false;
let canvas, ctx;

// === Init ===
document.addEventListener("DOMContentLoaded", () => {
  canvas = document.getElementById("sig-canvas");
  ctx = canvas.getContext("2d");

  // Scale canvas for retina
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * 2;
  canvas.height = rect.height * 2;
  ctx.scale(2, 2);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = "#1a1a2e";

  // Mouse events
  canvas.addEventListener("mousedown", startDraw);
  canvas.addEventListener("mousemove", draw);
  canvas.addEventListener("mouseup", stopDraw);
  canvas.addEventListener("mouseleave", stopDraw);

  // Touch events
  canvas.addEventListener("touchstart", (e) => { e.preventDefault(); startDraw(getTouchEvent(e)); });
  canvas.addEventListener("touchmove", (e) => { e.preventDefault(); draw(getTouchEvent(e)); });
  canvas.addEventListener("touchend", (e) => { e.preventDefault(); stopDraw(); });

  // Checkbox toggles submit button
  document.getElementById("agree-checkbox").addEventListener("change", updateSubmitState);

  // Initial preview
  updateTypedPreview();
});

// === Tab Switching ===
function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll(".sig-tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
  document.querySelector(`[data-tab="${tab}"]`).classList.add("active");
  document.getElementById(`tab-${tab}`).classList.add("active");
  updateSubmitState();
}

// === Typed Signature ===
function updateTypedPreview() {
  const input = document.getElementById("typed-name");
  const preview = document.getElementById("typed-preview");
  preview.textContent = input.value || "Your Name";
  updateSubmitState();
}

function renderTypedSignature() {
  const name = document.getElementById("typed-name").value;
  const renderCanvas = document.getElementById("typed-render-canvas");
  const rctx = renderCanvas.getContext("2d");
  renderCanvas.width = 560;
  renderCanvas.height = 160;
  rctx.clearRect(0, 0, 560, 160);
  rctx.font = "500 52px 'Dancing Script', cursive";
  rctx.fillStyle = "#1a1a2e";
  rctx.textBaseline = "middle";
  rctx.fillText(name, 20, 80);
  return renderCanvas.toDataURL("image/png");
}

// === Drawing Canvas ===
function getTouchEvent(e) {
  const touch = e.touches[0];
  const rect = canvas.getBoundingClientRect();
  return { offsetX: touch.clientX - rect.left, offsetY: touch.clientY - rect.top };
}

function startDraw(e) {
  isDrawing = true;
  ctx.beginPath();
  ctx.moveTo(e.offsetX, e.offsetY);
}

function draw(e) {
  if (!isDrawing) return;
  hasDrawn = true;
  ctx.lineTo(e.offsetX, e.offsetY);
  ctx.stroke();
  updateSubmitState();
}

function stopDraw() {
  isDrawing = false;
}

function clearCanvas() {
  const rect = canvas.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  hasDrawn = false;
  updateSubmitState();
}

function getDrawnSignature() {
  return canvas.toDataURL("image/png");
}

// === Validation ===
function updateSubmitState() {
  const agreed = document.getElementById("agree-checkbox").checked;
  let hasSignature = false;

  if (currentTab === "type") {
    hasSignature = document.getElementById("typed-name").value.trim().length > 0;
  } else {
    hasSignature = hasDrawn;
  }

  document.getElementById("submit-btn").disabled = !(agreed && hasSignature);
}

// === Submit ===
async function submitSignature() {
  const btn = document.getElementById("submit-btn");
  const statusEl = document.getElementById("status-message");

  btn.disabled = true;
  btn.textContent = "Signing...";
  statusEl.style.display = "none";

  let signatureData;
  let signatureType;

  if (currentTab === "type") {
    signatureData = renderTypedSignature();
    signatureType = "typed";
  } else {
    signatureData = getDrawnSignature();
    signatureType = "drawn";
  }

  try {
    const response = await fetch("/api/submit-signature", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token: TOKEN,
        signature_data: signatureData,
        signature_type: signatureType,
        signer_name: SIGNER_NAME,
      }),
    });

    const result = await response.json();

    if (response.ok) {
      document.getElementById("success-overlay").style.display = "flex";
    } else {
      statusEl.className = "status-message error";
      statusEl.textContent = result.detail || "An error occurred. Please try again.";
      statusEl.style.display = "block";
      btn.disabled = false;
      btn.textContent = "Sign Document";
    }
  } catch (err) {
    statusEl.className = "status-message error";
    statusEl.textContent = "Network error. Please check your connection and try again.";
    statusEl.style.display = "block";
    btn.disabled = false;
    btn.textContent = "Sign Document";
  }
}

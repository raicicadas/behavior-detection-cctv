// Shared storage + placeholder ripeness inference for the Avocado Ripeness Checker prototype.
// The PRD scopes real on-device model integration to a separate technical design doc,
// so classifyImage() below is a stand-in: it derives a plausible 1-5 stage from average
// pixel color so the UI/history flow can be built and demoed end-to-end today.

const HISTORY_KEY = "avocado_history";

const STAGE_COPY = {
  1: { status: "ripening", days: 4 },
  2: { status: "ripening", days: 3 },
  3: { status: "ripening", days: 1 },
  4: { status: "ready", days: 0 },
  5: { status: "ready", days: 0 },
};

function getHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
  } catch {
    return [];
  }
}

function saveHistoryEntry(entry) {
  const history = getHistory();
  history.unshift(entry);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

function getHistoryEntry(id) {
  return getHistory().find((e) => e.id === id) || null;
}

function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// Placeholder classifier: samples average brightness/greenness from the photo.
// Darker + less saturated -> riper (closer to stage 5). Purely illustrative.
function classifyImage(dataUrl) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      const size = 64;
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, size, size);

      let rSum = 0,
        gSum = 0,
        bSum = 0;
      const { data } = ctx.getImageData(0, 0, size, size);
      for (let i = 0; i < data.length; i += 4) {
        rSum += data[i];
        gSum += data[i + 1];
        bSum += data[i + 2];
      }
      const pixelCount = data.length / 4;
      const rAvg = rSum / pixelCount;
      const gAvg = gSum / pixelCount;
      const bAvg = bSum / pixelCount;
      const brightness = (rAvg + gAvg + bAvg) / 3;

      // darker average brightness -> assume further along ripening (skin darkens)
      const stage = Math.min(5, Math.max(1, Math.round(((255 - brightness) / 255) * 4) + 1));
      const confidence = Math.round(55 + Math.random() * 40);

      resolve({ stage, confidence });
    };
    img.src = dataUrl;
  });
}

function formatDate(iso) {
  const d = new Date(iso);
  return `${d.getMonth() + 1}월 ${d.getDate()}일`;
}

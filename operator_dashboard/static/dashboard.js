const charts = {
  voltage: document.getElementById("voltage-chart"),
  power: document.getElementById("power-chart"),
  frequency: document.getElementById("frequency-chart"),
};

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function formatNumber(value, unit) {
  if (value === undefined || value === null || value === "") return "--";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return `${number.toFixed(2)} ${unit}`;
}

function seriesRange(seriesList) {
  const values = seriesList.flatMap((series) => series.values).filter(Number.isFinite);
  if (!values.length) return [0, 1];
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const pad = (max - min) * 0.12;
  return [min - pad, max + pad];
}

function drawChart(canvas, seriesList, unit) {
  if (!canvas) return;
  const styles = getComputedStyle(document.documentElement);
  const chartBg = styles.getPropertyValue("--chart-bg").trim() || "#071016";
  const chartGrid = styles.getPropertyValue("--chart-grid").trim() || "rgba(145,167,180,0.16)";
  const chartText = styles.getPropertyValue("--muted").trim() || "#91a7b4";
  const rect = canvas.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * scale));
  canvas.height = Math.max(1, Math.floor(rect.height * scale));

  const ctx = canvas.getContext("2d");
  ctx.scale(scale, scale);

  const width = rect.width;
  const height = rect.height;
  const pad = 34;
  ctx.clearRect(0, 0, width, height);

  ctx.fillStyle = chartBg;
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = chartGrid;
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = pad + ((height - pad * 2) * i) / 4;
    ctx.beginPath();
    ctx.moveTo(pad, y);
    ctx.lineTo(width - pad, y);
    ctx.stroke();
  }

  const [min, max] = seriesRange(seriesList);
  ctx.fillStyle = chartText;
  ctx.font = "12px system-ui";
  ctx.fillText(`${max.toFixed(1)} ${unit}`, pad, 18);
  ctx.fillText(`${min.toFixed(1)} ${unit}`, pad, height - 10);

  seriesList.forEach((series) => {
    const values = series.values.filter(Number.isFinite);
    if (!values.length) return;
    ctx.strokeStyle = series.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    values.forEach((value, index) => {
      const x = pad + ((width - pad * 2) * index) / Math.max(1, values.length - 1);
      const y = height - pad - ((value - min) / (max - min)) * (height - pad * 2);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.fillStyle = series.color;
    ctx.fillText(series.label, width - pad - 58, 18 + seriesList.indexOf(series) * 16);
  });
}

function updateDashboard(data) {
  setText("server-state", data.serverRunning ? "Running" : "Stopped");
  setText("database-state", data.databaseOnline ? "Online" : "Missing");
  setText("log-state", data.runtimeLogOnline ? "Enabled" : "Waiting");
  setText("end-device-count", String(data.tableCounts?.end_devices ?? 0));

  const latest = data.latestMeasurement || {};
  setText("voltage-a", formatNumber(latest.voltage_a, "V"));
  setText("voltage-b", formatNumber(latest.voltage_b, "V"));
  setText("voltage-c", formatNumber(latest.voltage_c, "V"));
  setText("frequency", formatNumber(latest.frequency, "Hz"));

  const log = document.getElementById("runtime-log");
  if (log && Array.isArray(data.logs)) {
    log.textContent = data.logs.join("\n");
    log.scrollTop = log.scrollHeight;
  }

  const history = Array.isArray(data.history) ? data.history : [];
  drawChart(
    charts.voltage,
    [
      { label: "Va", color: "#25d0b0", values: history.map((row) => Number(row.voltage_a)) },
      { label: "Vb", color: "#5fb2ff", values: history.map((row) => Number(row.voltage_b)) },
      { label: "Vc", color: "#ffc857", values: history.map((row) => Number(row.voltage_c)) },
    ],
    "V"
  );
  drawChart(
    charts.power,
    [
      { label: "Pa", color: "#25d0b0", values: history.map((row) => Number(row.power_a)) },
      { label: "Pb", color: "#5fb2ff", values: history.map((row) => Number(row.power_b)) },
      { label: "Pc", color: "#ffc857", values: history.map((row) => Number(row.power_c)) },
    ],
    "KW"
  );
  drawChart(
    charts.frequency,
    [{ label: "Hz", color: "#e879f9", values: history.map((row) => Number(row.frequency)) }],
    "Hz"
  );
}

async function pollLiveData() {
  if (!document.getElementById("voltage-chart")) return;
  try {
    const response = await fetch("/api/live", { cache: "no-store" });
    if (!response.ok) return;
    updateDashboard(await response.json());
  } catch (error) {
    // Keep the UI stable when the dashboard is restarted.
  }
}

pollLiveData();
setInterval(pollLiveData, 2000);
window.addEventListener("resize", pollLiveData);
window.addEventListener("themechange", pollLiveData);

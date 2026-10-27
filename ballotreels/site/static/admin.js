// Queue monitor: polls /admin/api/jobs and lets the operator retry,
// cancel, requeue or regenerate a job. The admin cookie set by /admin/login
// authorises every fetch here automatically (same-origin).

function clock(epoch) {
  return epoch == null ? "" : new Date(epoch * 1000).toLocaleTimeString();
}

function seconds(n) {
  return n == null ? "" : `${n.toFixed(1)}s`;
}

// One line per stage: start time, finish time and duration.
function stageLines(stages) {
  return Object.entries(stages || {}).map(([name, t]) =>
    `${name}: ${clock(t.start)} - ${clock(t.finish)} ${seconds(t.duration)}`)
    .join("\n");
}

async function refresh() {
  const resp = await fetch("/admin/api/jobs");
  if (!resp.ok) return;
  const doc = await resp.json();

  const summary = document.getElementById("summary");
  const medianMinutes = doc.median_seconds == null
    ? "none yet" : Math.round(doc.median_seconds / 60) + " min";
  summary.textContent =
    `queue depth: ${doc.depth} · median job time: ${medianMinutes} · ` +
    `workers: ${doc.workers.map((w) => `${w.id} (last seen ${new Date(w.last_seen * 1000).toLocaleTimeString()})`).join(", ") || "none"}`;

  const tbody = document.querySelector("#jobs tbody");
  tbody.innerHTML = "";
  for (const job of doc.jobs) {
    const row = document.createElement("tr");
    const cell = (text) => {
      const td = document.createElement("td");
      td.textContent = text == null ? "" : text;
      return td;
    };
    row.appendChild(cell(job.id));
    row.appendChild(cell(job.key));
    row.appendChild(cell(job.state));
    row.appendChild(cell(job.stage));
    row.appendChild(cell(job.worker_id));
    row.appendChild(cell(clock(job.last_heartbeat)));
    const stagesCell = cell(stageLines(job.stages));
    stagesCell.className = "stages";
    row.appendChild(stagesCell);
    const errCell = cell(job.error);
    errCell.className = "error";
    row.appendChild(errCell);

    const actionsCell = document.createElement("td");
    for (const action of ["retry", "cancel", "requeue", "regenerate"]) {
      const button = document.createElement("button");
      button.textContent = action;
      button.onclick = () => act(job.id, action);
      actionsCell.appendChild(button);
    }
    row.appendChild(actionsCell);
    tbody.appendChild(row);
  }
}

async function act(jobId, action) {
  const message = document.getElementById("message");
  const resp = await fetch(`/admin/api/jobs/${jobId}/${action}`,
                           { method: "POST" });
  if (resp.ok) {
    message.textContent = "";
  } else {
    const body = await resp.json().catch(() => null);
    message.textContent = `job #${jobId}: ${action} failed: ` +
      (body && body.error ? body.error : `HTTP ${resp.status}`);
  }
  refresh();
}

refresh();
setInterval(refresh, 5000);

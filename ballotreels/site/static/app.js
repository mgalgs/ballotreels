// ballotreels phone UI: a hash router over the public JSON API. No
// build step, no framework. Map drawing uses Leaflet when it is loaded
// (see index.html) and falls back to a plain inline SVG when it is
// not, e.g. offline.

const REPORT_URL = "https://github.com/mgalgs/ballotreels/issues";

// The standard's rule 4.1: one neutral colour for every district and
// the zip outline on the map; the outline is told apart by dash, not
// colour. A grey, so it can't be taken for a partisan red or blue. This is
// the only colour literal map drawing uses.
const MAP_COLOR = "#666666";

const app = document.getElementById("app");

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children || []) node.appendChild(child);
  return node;
}

async function getJson(path) {
  const resp = await fetch(path);
  const body = await resp.json().catch(() => null);
  return { ok: resp.ok, status: resp.status, body };
}

async function postJson(path, data) {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const body = await resp.json().catch(() => null);
  return { ok: resp.ok, status: resp.status, body, headers: resp.headers };
}

// -- map drawing -----------------------------------------------------

// `onSelect(ocdId)` is called when a district is tapped; the zip outline
// is drawn underneath and takes no taps.
function drawMap(container, featureCollection, onSelect) {
  container.innerHTML = "";
  if (typeof L === "undefined") {
    drawFallbackSvg(container, featureCollection, onSelect);
    return;
  }
  const map = L.map(container, { attributionControl: true });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  const bounds = [];
  for (const feature of featureCollection.features) {
    const isZip = feature.properties.role === "zip";
    const rings = feature.geometry.coordinates.map(
      (ring) => ring.map(([x, y]) => [y, x]));
    const layer = L.polygon(rings, {
      color: MAP_COLOR,
      weight: 2,
      fillColor: MAP_COLOR,
      fillOpacity: isZip ? 0.05 : 0.2,
      dashArray: isZip ? "4 4" : null,
      interactive: !isZip,
    }).addTo(map);
    if (!isZip && onSelect) {
      layer.bindTooltip(feature.properties.name);
      layer.on("click", () => onSelect(feature.properties.ocd_id));
    }
    layer.getBounds().getSouthWest() && bounds.push(layer.getBounds());
  }
  if (bounds.length) {
    let combined = bounds[0];
    for (const b of bounds.slice(1)) combined = combined.extend(b);
    map.fitBounds(combined, { padding: [10, 10] });
  }
}

function drawFallbackSvg(container, featureCollection, onSelect) {
  const xs = [];
  const ys = [];
  for (const feature of featureCollection.features) {
    for (const ring of feature.geometry.coordinates) {
      for (const [x, y] of ring) {
        xs.push(x);
        ys.push(y);
      }
    }
  }
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const w = 300, h = 220;
  const sx = (x) => ((x - minX) / (maxX - minX || 1)) * w;
  const sy = (y) => h - ((y - minY) / (maxY - minY || 1)) * h;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("width", "100%");
  for (const feature of featureCollection.features) {
    const isZip = feature.properties.role === "zip";
    for (const ring of feature.geometry.coordinates) {
      const points = ring.map(([x, y]) => `${sx(x)},${sy(y)}`).join(" ");
      const poly = document.createElementNS(
        "http://www.w3.org/2000/svg", "polygon");
      poly.setAttribute("points", points);
      poly.setAttribute("stroke", MAP_COLOR);
      poly.setAttribute("fill", MAP_COLOR);
      poly.setAttribute("fill-opacity", isZip ? "0.05" : "0.2");
      poly.setAttribute("stroke-width", "2");
      if (isZip) {
        poly.setAttribute("stroke-dasharray", "4 4");
        poly.setAttribute("pointer-events", "none");
      } else if (onSelect) {
        poly.style.cursor = "pointer";
        poly.addEventListener("click",
          () => onSelect(feature.properties.ocd_id));
      }
      svg.appendChild(poly);
    }
  }
  container.appendChild(svg);
  container.appendChild(el("p", {
    text: "Map data © OpenStreetMap contributors",
  }));
}

// -- routes -----------------------------------------------------------

function parseHash() {
  const hash = location.hash.replace(/^#/, "") || "/";
  const [path, query] = hash.split("?");
  const params = new URLSearchParams(query || "");
  return { path, params };
}

async function route() {
  const { path, params } = parseHash();
  app.innerHTML = "";
  if (path === "/" || path === "") return renderHome();
  let m = path.match(/^\/zip\/([0-9]+)$/);
  if (m) return renderZip(m[1]);
  if (path === "/address") return renderAddress();
  if (path === "/ballot") return renderBallot(params.getAll("d"), params.get("addr"));
  m = path.match(/^\/contest\/(.+)$/);
  if (m) return renderContest(m[1]);
  app.appendChild(el("p", { text: "Page not found." }));
}

function renderHome() {
  const input = el("input", { type: "text", inputmode: "numeric",
                              placeholder: "Zip code", maxlength: "5" });
  const go = () => {
    const zip = input.value.trim();
    if (/^\d{5}$/.test(zip)) location.hash = `#/zip/${zip}`;
  };
  app.appendChild(el("section", {}, [
    el("h2", { text: "Find your ballot" }),
    input,
    el("button", { text: "Continue", onclick: go }),
    el("p", {}, [
      el("a", { href: "#/address", text: "enter your address instead" }),
    ]),
  ]));
}

async function renderAddress() {
  const input = el("input", { type: "text", placeholder: "Street address" });
  const result = el("div", {});
  const go = async () => {
    result.textContent = "Looking that up...";
    const { ok, status, body } = await postJson("/api/address",
      { address: input.value });
    if (!ok) {
      result.textContent = body && body.error ? body.error :
        "We couldn't find that address.";
      return;
    }
    const divisions = [];
    for (const entries of Object.values(body.kinds)) {
      for (const entry of entries) divisions.push(entry.ocd_id);
    }
    // The geocoder's matched address rides along in the hash so the
    // ballot page can show it and the voter can check it.
    const params = divisions.map((d) => `d=${encodeURIComponent(d)}`)
      .concat([`addr=${encodeURIComponent(body.matched_address || "")}`])
      .join("&");
    location.hash = `#/ballot?${params}`;
  };
  app.appendChild(el("section", {}, [
    el("h2", { text: "Enter your address" }),
    input,
    el("button", { text: "Continue", onclick: go }),
    result,
  ]));
}

async function renderZip(zip) {
  const { ok, body } = await getJson(`/api/zip/${zip}`);
  if (!ok) {
    app.appendChild(el("p", { text: body && body.error ?
      body.error : "We couldn't find that zip code." }));
    return;
  }
  if (body.ambiguous.length === 0) {
    const divisions = [];
    for (const entries of Object.values(body.kinds)) {
      for (const entry of entries) divisions.push(entry.ocd_id);
    }
    // The geocoder's matched address rides along in the hash so the
    // ballot page can show it and the voter can check it.
    const params = divisions.map((d) => `d=${encodeURIComponent(d)}`)
      .concat([`addr=${encodeURIComponent(body.matched_address || "")}`])
      .join("&");
    location.hash = `#/ballot?${params}`;
    return;
  }
  await renderAmbiguousKind(zip, body, body.ambiguous[0]);
}

async function renderAmbiguousKind(zip, zipDoc, kind) {
  app.innerHTML = "";
  const mapDiv = el("div", { class: "map-container" });
  app.appendChild(el("section", {}, [
    el("h2", { text: "Select your district" }),
    mapDiv,
  ]));
  const { body: shapes } = await getJson(
    `/api/zip/${zip}/shapes?kind=${encodeURIComponent(kind)}`);
  if (shapes) {
    drawMap(mapDiv, shapes,
      (ocdId) => selectDistrict(zip, zipDoc, kind, ocdId));
  }

  const list = el("ul", { class: "district-list" });
  for (const entry of zipDoc.kinds[kind]) {
    list.appendChild(el("li", {
      text: entry.name,
      onclick: () => selectDistrict(zip, zipDoc, kind, entry.ocd_id),
    }));
  }
  app.appendChild(el("section", {}, [list]));
}

function selectDistrict(zip, zipDoc, chosenKind, chosenOcdId) {
  // Narrow the chosen kind to the one district picked, so that a later
  // step (the next ambiguous kind) carries this choice forward.
  const kinds = { ...zipDoc.kinds, [chosenKind]: [{ ocd_id: chosenOcdId }] };
  const remaining = zipDoc.ambiguous.filter((k) => k !== chosenKind);
  if (remaining.length > 0) {
    // Ask about the next ambiguous kind before going to the ballot.
    renderAmbiguousKind(zip, { ...zipDoc, kinds, ambiguous: remaining },
      remaining[0]);
    return;
  }
  const divisions = [];
  for (const entries of Object.values(kinds)) {
    for (const entry of entries) divisions.push(entry.ocd_id);
  }
  const params = divisions.map((d) => `d=${encodeURIComponent(d)}`).join("&");
  location.hash = `#/ballot?${params}`;
}

const LEVEL_NAMES = {
  state: "Statewide",
  cd: "Congressional",
  sldu: "State Senate",
  sldl: "State Assembly",
  county: "County",
};

async function renderBallot(divisions, matchedAddress) {
  const query = divisions.map((d) => `d=${encodeURIComponent(d)}`).join("&");
  const { ok, body } = await getJson(`/api/ballot?${query}`);
  if (!ok) {
    app.appendChild(el("p", { text: "We couldn't load your ballot." }));
    return;
  }
  const section = el("section", {}, [el("h2", { text: "Your ballot" })]);
  if (matchedAddress) {
    section.appendChild(el("p", { class: "matched-address" }, [
      el("span", { text: `Matched address: ${matchedAddress}. ` }),
      el("a", { href: "#/address", text: "Not your address? Try again" }),
    ]));
  }
  for (const level of body.levels) {
    section.appendChild(el("div", { class: "level-heading",
                                    text: LEVEL_NAMES[level.level] || level.level }));
    for (const contest of level.contests) {
      section.appendChild(renderContestCard(contest));
    }
  }
  app.appendChild(section);
}

function renderContestCard(contest) {
  const card = el("div", { class: "contest" }, [
    el("h3", { text: contest.title }),
  ]);
  if (contest.kind === "race" && contest.status === "unavailable") {
    card.appendChild(el("p", { text: "Not available yet." }));
    return card;
  }
  if (contest.status === "cached") {
    card.appendChild(el("a", { href: `#/contest/${contest.id}`,
                              text: "Watch the video" }));
    return card;
  }
  if ((contest.status === "queued" || contest.status === "running") &&
      contest.job) {
    const status = el("p", {
      text: `Generating${contest.job.position != null ?
        ` (position ${contest.job.position})` : ""}` +
        `${contest.job.eta_minutes != null ?
          `, about ${contest.job.eta_minutes} min` : ""}...`,
    });
    card.appendChild(status);
    pollJob(contest.id, contest.job.id, status);
    return card;
  }
  const status = el("p", { text: "No video yet." });
  card.appendChild(status);
  const button = el("button", {
    text: "Generate",
    onclick: async () => {
      button.disabled = true;
      status.textContent = "Starting...";
      const { status: httpStatus, body } = await postJson(
        "/api/generate", { contest: contest.id });
      if (httpStatus === 429) {
        status.textContent = "Please try again later.";
        return;
      }
      if (body && body.status === "cached") {
        location.hash = `#/contest/${contest.id}`;
        return;
      }
      pollJob(contest.id, body.job.id, status);
    },
  });
  card.appendChild(button);
  return card;
}

// Polls one job until it ends, updating its status line in place. A poll
// stops as soon as its status line has left the page (the voter moved on,
// or the ballot re-rendered), so polls never pile up or pull the voter
// to another page.
async function pollJob(contestId, jobId, statusEl) {
  const { body } = await getJson(`/api/jobs/${jobId}`);
  if (!body || !statusEl.isConnected) return;
  if (body.state === "done") {
    statusEl.textContent = "";
    statusEl.appendChild(el("a", { href: `#/contest/${contestId}`,
                                   text: "Watch the video" }));
    return;
  }
  if (body.state === "failed") {
    statusEl.textContent = failureMessage(body.failed_stage);
    return;
  }
  if (body.state !== "queued" && body.state !== "running") {
    statusEl.textContent = "No video yet.";
    return;
  }
  const position = body.position != null ? ` (position ${body.position})` : "";
  const eta = body.eta_minutes != null ? `, about ${body.eta_minutes} min` : "";
  statusEl.textContent = `Generating${position}${eta}...`;
  setTimeout(() => pollJob(contestId, jobId, statusEl), 4000);
}

function failureMessage(stage) {
  if (stage === "sources") return "Sources for this contest haven't been archived yet.";
  if (stage === "script") return "Automatic script writing isn't built yet.";
  return "This video couldn't be made. The operator has been notified by the queue.";
}

async function renderContest(contestId) {
  const { ok, body } = await getJson(`/api/contest/${contestId}`);
  if (!ok) {
    app.appendChild(el("p", { text: "We couldn't find that contest." }));
    return;
  }
  const section = el("section", {}, [el("h2", { text: body.title })]);
  if (body.video_url) {
    section.appendChild(el("video", { src: body.video_url,
                                      poster: body.poster_url || "",
                                      controls: "controls" }));
  } else {
    section.appendChild(el("p", { text: "No video yet." }));
  }
  section.appendChild(el("p", { text: `Standard version ${body.standard_version}` }));
  if (body.corrections && body.corrections.length) {
    const list = el("ul", {});
    for (const c of body.corrections) {
      list.appendChild(el("li", { text: `${c.date}: ${c.note}` }));
    }
    section.appendChild(el("h3", { text: "Corrections" }));
    section.appendChild(list);
  }
  section.appendChild(el("h3", { text: "Sources" }));
  const sourceList = el("ul", { class: "source-list" });
  for (const source of body.sources || []) {
    sourceList.appendChild(el("li", {}, [
      el("a", { href: source.url, text: source.publisher || source.url }),
    ]));
  }
  section.appendChild(sourceList);
  section.appendChild(el("p", {}, [
    el("a", { href: body.report_url || REPORT_URL,
             text: "Report an error with this video" }),
  ]));
  app.appendChild(section);
}

// The script tag is the last thing in <body>, so the DOM (and #app) is
// already parsed by the time this runs; only hash changes need a
// listener after the first route().
window.addEventListener("hashchange", route);
route();

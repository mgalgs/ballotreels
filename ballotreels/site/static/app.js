// ballotreels phone UI: a hash router over the public JSON API. No
// build step, no framework. Map drawing uses Leaflet when it is loaded
// (see index.html) and falls back to a plain inline SVG when it is
// not, e.g. offline.

const REPORT_URL = "https://github.com/mgalgs/ballotreels/issues";
const STANDARD_URL =
  "https://github.com/mgalgs/ballotreels/blob/main/docs/STANDARD.md";

// The standard's rule 4.1: one neutral colour for every district and
// the zip outline on the map; the outline is told apart by dash, not
// colour. A grey, so it can't be taken for a partisan red or blue. This is
// the only colour literal map drawing uses.
const MAP_COLOR = "#666666";

// Districts are told apart by a letter pinned on the map (and on their
// card in the list) and by their line's dash, never by colour.
const DISTRICT_DASHES = [null, "12 7", "18 5 3 5", "3 6"];
const ZIP_DASH = "4 4";

const app = document.getElementById("app");

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children || []) {
    if (child == null) continue;
    node.appendChild(typeof child === "string" ?
      document.createTextNode(child) : child);
  }
  return node;
}

// Small pencil-drawn icons. They are drawn in currentColor or the
// stylesheet's one accent, so this file keeps a single colour literal.
const ICONS = {
  play: '<svg viewBox="0 0 22 22" aria-hidden="true"><circle cx="11" ' +
    'cy="11" r="9.5" fill="none" stroke="currentColor" stroke-width="1.8"/>' +
    '<path d="M9 7 L15.5 11 L9 15 Z" fill="currentColor" ' +
    'stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/></svg>',
  pencil: '<svg viewBox="0 0 30 30" aria-hidden="true"><path d="M6 24 ' +
    'L8 17 L20 5 L25 10 L13 22 Z M8 17 L13 22 M18 7 L23 12" ' +
    'fill="none" stroke="currentColor" stroke-width="1.7" ' +
    'stroke-linejoin="round" stroke-linecap="round" opacity="0.6"/></svg>',
  lost: '<svg viewBox="0 0 54 54" aria-hidden="true"><path d="M27 4 C 13 ' +
    '5, 5 14, 5 27 C 6 41, 15 49, 28 49 C 41 48, 49 39, 49 26 C 48 13, ' +
    '39 5, 26 5" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round"/><path d="M20 21 C 20 15, 34 14, 34 21 C 34 ' +
    '26, 27 26, 27 31" fill="none" style="stroke:var(--accent)" ' +
    'stroke-width="2.6" stroke-linecap="round"/><circle cx="27" cy="38" ' +
    'r="1.9" style="fill:var(--accent)"/></svg>',
};

function icon(name, cls) {
  const span = el("span", { class: cls || "icon", "aria-hidden": "true" });
  span.innerHTML = ICONS[name];
  return span;
}

// A heading with the video's orange pencil line under its words.
function heading(tag, text, attrs) {
  return el(tag, attrs || {}, [el("span", { class: "scribble", text })]);
}

function button(text, attrs) {
  return el("button", { type: "button", class: "btn", text, ...attrs });
}

function linkButton(text, href, cls) {
  return el("a", { class: `btn ${cls || ""}`.trim(), href, text });
}

function backLink(text, href) {
  return el("a", { class: "back", href, text: `‹ ${text}` });
}

function loading(text) {
  return el("div", { class: "loading", role: "status" }, [
    el("span", { class: "pencil-spin" }),
    el("span", { text }),
  ]);
}

// A styled error or empty state, always with a way back.
function notice(title, message, actions) {
  return el("section", { class: "box notice", role: "alert" }, [
    icon("lost", "notice-mark"),
    el("h2", { text: title }),
    el("p", { text: message }),
    el("div", { class: "btn-row" }, actions),
  ]);
}

function homeActions() {
  return [
    linkButton("Try another zip", "#/", "btn-primary"),
    linkButton("Use my address", "#/address", "btn-quiet"),
  ];
}

// Fetch failures (offline, server down) come back as status 0 rather
// than throwing, so every page can show its own message for them.
async function getJson(path) {
  try {
    const resp = await fetch(path);
    const body = await resp.json().catch(() => null);
    return { ok: resp.ok, status: resp.status, body };
  } catch (e) {
    return { ok: false, status: 0, body: null };
  }
}

async function postJson(path, data) {
  try {
    const resp = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const body = await resp.json().catch(() => null);
    return { ok: resp.ok, status: resp.status, body, headers: resp.headers };
  } catch (e) {
    return { ok: false, status: 0, body: null, headers: new Headers() };
  }
}

function offlineNotice() {
  return notice("We couldn't reach ballotreels",
    "Check your connection and try again.",
    [button("Try again", { class: "btn btn-primary", onclick: route }),
     linkButton("Start over", "#/", "btn-quiet")]);
}

// -- map drawing -----------------------------------------------------

function letterFor(i) {
  return String.fromCharCode(65 + i);
}

// Even-odd ray cast over a polygon's rings ([x, y] = [lon, lat]).
function insidePolygon(x, y, rings) {
  let inside = false;
  for (const ring of rings) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i];
      const [xj, yj] = ring[j];
      if ((yi > y) !== (yj > y) &&
          x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
    }
  }
  return inside;
}

function ringsBox(rings) {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const ring of rings) {
    for (const [x, y] of ring) {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    }
  }
  return { minX, maxX, minY, maxY };
}

// Where to pin a district's letter: the middle of the part of it that
// lies within the zip (that is where the choice matters), or the middle
// of the district if none of a coarse grid over the zip falls in it.
function labelPoint(districtRings, zipRings) {
  const box = ringsBox(zipRings || districtRings);
  let sx = 0, sy = 0, n = 0;
  const steps = 24;
  for (let i = 0; i <= steps; i++) {
    for (let j = 0; j <= steps; j++) {
      const x = box.minX + ((box.maxX - box.minX) * i) / steps;
      const y = box.minY + ((box.maxY - box.minY) * j) / steps;
      if (insidePolygon(x, y, districtRings) &&
          (!zipRings || insidePolygon(x, y, zipRings))) {
        sx += x; sy += y; n++;
      }
    }
  }
  if (n) return [sx / n, sy / n];
  const own = ringsBox(districtRings);
  return [(own.minX + own.maxX) / 2, (own.minY + own.maxY) / 2];
}

// `onSelect(ocdId)` is called when a district is tapped; the zip outline
// is drawn on top and takes no taps. `letters` maps an ocd id to the
// letter its card in the list shows.
function drawMap(container, featureCollection, onSelect, letters) {
  container.innerHTML = "";
  if (typeof L === "undefined") {
    drawFallbackSvg(container, featureCollection, onSelect, letters);
    return;
  }
  const map = L.map(container, { attributionControl: true,
                                 scrollWheelZoom: false });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  const zip = featureCollection.features.find(
    (f) => f.properties.role === "zip");
  const zipRings = zip ? zip.geometry.coordinates : null;
  const bounds = [];
  let zipBounds = null;
  let n = 0;
  for (const feature of featureCollection.features) {
    const isZip = feature.properties.role === "zip";
    const rings = feature.geometry.coordinates.map(
      (ring) => ring.map(([x, y]) => [y, x]));
    const dash = isZip ? ZIP_DASH : DISTRICT_DASHES[n % DISTRICT_DASHES.length];
    const layer = L.polygon(rings, {
      color: MAP_COLOR,
      weight: isZip ? 3 : 2.5,
      fillColor: MAP_COLOR,
      fillOpacity: isZip ? 0 : 0.12,
      dashArray: dash,
      interactive: !isZip,
    }).addTo(map);
    if (isZip) {
      zipBounds = layer.getBounds();
    } else {
      n++;
      const letter = letters && letters[feature.properties.ocd_id];
      if (letter) {
        const [x, y] = labelPoint(feature.geometry.coordinates, zipRings);
        L.tooltip({ permanent: true, direction: "center",
                    className: "district-label", interactive: false })
          .setLatLng([y, x]).setContent(letter).addTo(map);
      }
      if (onSelect) {
        layer.on("click", () => onSelect(feature.properties.ocd_id));
      }
    }
    layer.getBounds().getSouthWest() && bounds.push(layer.getBounds());
  }
  // Frame the zip, where the districts split; fall back to everything.
  if (zipBounds) {
    map.fitBounds(zipBounds.pad(0.3));
  } else if (bounds.length) {
    let combined = bounds[0];
    for (const b of bounds.slice(1)) combined = combined.extend(b);
    map.fitBounds(combined, { padding: [10, 10] });
  }
  // The zip outline on top, so it is never hidden under a district.
  map.eachLayer((layer) => {
    if (layer.options && layer.options.dashArray === ZIP_DASH &&
        layer.bringToFront) layer.bringToFront();
  });
}

function drawFallbackSvg(container, featureCollection, onSelect, letters) {
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
  const w = 300, h = 220, pad = 10;
  const sx = (x) => pad + ((x - minX) / (maxX - minX || 1)) * (w - 2 * pad);
  const sy = (y) => h - pad - ((y - minY) / (maxY - minY || 1)) * (h - 2 * pad);
  const ns = "http://www.w3.org/2000/svg";

  const zip = featureCollection.features.find(
    (f) => f.properties.role === "zip");
  const zipRings = zip ? zip.geometry.coordinates : null;
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", "100%");
  const labels = [];
  let n = 0;
  // Districts first, the zip outline last so it sits on top.
  const ordered = featureCollection.features.slice().sort(
    (a, b) => (a.properties.role === "zip") - (b.properties.role === "zip"));
  for (const feature of ordered) {
    const isZip = feature.properties.role === "zip";
    const dash = isZip ? ZIP_DASH : DISTRICT_DASHES[n % DISTRICT_DASHES.length];
    if (!isZip) n++;
    for (const ring of feature.geometry.coordinates) {
      const points = ring.map(([x, y]) => `${sx(x)},${sy(y)}`).join(" ");
      const poly = document.createElementNS(ns, "polygon");
      poly.setAttribute("points", points);
      poly.setAttribute("stroke", MAP_COLOR);
      poly.setAttribute("fill", MAP_COLOR);
      poly.setAttribute("fill-opacity", isZip ? "0" : "0.12");
      poly.setAttribute("stroke-width", isZip ? "2.5" : "2");
      if (dash) poly.setAttribute("stroke-dasharray", dash);
      if (isZip) {
        poly.setAttribute("pointer-events", "none");
      } else if (onSelect) {
        poly.style.cursor = "pointer";
        poly.addEventListener("click",
          () => onSelect(feature.properties.ocd_id));
      }
      svg.appendChild(poly);
    }
    const letter = !isZip && letters && letters[feature.properties.ocd_id];
    if (letter) {
      const [x, y] = labelPoint(feature.geometry.coordinates, zipRings);
      const text = document.createElementNS(ns, "text");
      text.setAttribute("x", sx(x));
      text.setAttribute("y", sy(y));
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("dominant-baseline", "central");
      text.setAttribute("class", "svg-label");
      text.setAttribute("fill", "currentColor");
      text.setAttribute("pointer-events", "none");
      text.textContent = letter;
      labels.push(text);
    }
  }
  for (const text of labels) svg.appendChild(text);
  container.appendChild(svg);
}

// -- routes -----------------------------------------------------------

function parseHash() {
  const hash = location.hash.replace(/^#/, "") || "/";
  const [path, query] = hash.split("?");
  const params = new URLSearchParams(query || "");
  return { path, params };
}

// Bumped on every route() call. A render that awaits the server checks
// it afterwards and drops its result if the voter has moved on, so a
// late response never replaces the page they are now on.
let routeToken = 0;

function isStale(token) {
  return token !== routeToken;
}

async function route() {
  routeToken += 1;
  const { path, params } = parseHash();
  app.innerHTML = "";
  window.scrollTo(0, 0);
  if (path === "/" || path === "") return renderHome();
  let m = path.match(/^\/zip\/([0-9]+)$/);
  if (m) return renderZip(m[1]);
  if (path === "/address") return renderAddress();
  if (path === "/ballot") return renderBallot(params.getAll("d"), params.get("addr"));
  m = path.match(/^\/contest\/(.+)$/);
  if (m) return renderContest(m[1]);
  app.appendChild(notice("Page not found",
    "That link doesn't go anywhere on ballotreels.",
    [linkButton("Find your ballot", "#/", "btn-primary")]));
}

function renderHome() {
  const input = el("input", {
    type: "text", id: "zip", class: "zip-input", inputmode: "numeric",
    pattern: "[0-9]*", autocomplete: "postal-code", maxlength: "5",
    placeholder: "5 digits", autofocus: "autofocus",
    "aria-describedby": "zip-note",
  });
  const note = el("p", { id: "zip-note", class: "field-note",
                         "aria-live": "polite" });
  const form = el("form", {
    class: "box", novalidate: "novalidate",
    onsubmit: (event) => {
      event.preventDefault();
      const zip = input.value.trim();
      if (/^\d{5}$/.test(zip)) {
        location.hash = `#/zip/${zip}`;
      } else {
        note.textContent = "A zip code is 5 digits.";
        input.focus();
      }
    },
  }, [
    el("label", { for: "zip", text: "Your zip code" }),
    input,
    note,
    el("button", { type: "submit", class: "btn btn-primary btn-block",
                   text: "Show my ballot" }),
  ]);
  input.addEventListener("input", () => { note.textContent = ""; });

  app.appendChild(el("section", { class: "hero" }, [
    heading("h1", "Your ballot, explained"),
    el("p", { class: "lead",
              text: "Short, even-handed videos on everything on your " +
                    "ballot, with every claim sourced." }),
    form,
    el("div", { class: "or-rule", text: "or" }),
    linkButton("Use my street address", "#/address", "btn-quiet btn-block"),
    el("p", { class: "field-note",
              text: "Pins down your exact districts when a zip code " +
                    "spans more than one." }),
  ]));
  app.appendChild(el("section", { class: "scrap" }, [
    el("p", { class: "promise-title", text: "How the videos are made" }),
    el("ul", { class: "promise" }, [
      el("li", { text: "Every claim names its source, listed under the video." }),
      el("li", { text: "Both sides get the same time and the same number of words." }),
      el("li", { text: "Bias is a bug: if you spot it, report it." }),
    ]),
  ]));
  input.focus();
}

async function renderAddress() {
  const input = el("input", {
    type: "text", id: "address", autocomplete: "street-address",
    placeholder: "123 Main St, San Jose, CA 95112",
    enterkeyhint: "search", "aria-describedby": "address-note",
  });
  const result = el("div", { id: "address-note", "aria-live": "polite" });
  const submit = el("button", { type: "submit",
                                class: "btn btn-primary btn-block",
                                text: "Find my ballot" });
  const go = async () => {
    if (!input.value.trim()) {
      result.replaceChildren(el("p", { class: "inline-error",
        text: "Type your street address, with the city and zip." }));
      input.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "Looking it up...";
    result.replaceChildren();
    const token = routeToken;
    const { ok, status, body } = await postJson("/api/address",
      { address: input.value });
    if (isStale(token)) return;
    if (!ok) {
      submit.disabled = false;
      submit.textContent = "Find my ballot";
      let message;
      if (status === 404) {
        message = "We couldn't find that address. Check the spelling " +
          "and include the city and zip.";
      } else if (status === 0) {
        message = "We couldn't reach ballotreels. Check your connection " +
          "and try again.";
      } else if (status === 502 || status === 503) {
        message = "The address lookup isn't answering right now. Try " +
          "again in a minute, or use your zip code.";
      } else if (status === 429) {
        message = "You've looked up several addresses in a short time. " +
          "Try again later, or use your zip code.";
      } else {
        message = body && body.error ? body.error :
          "We couldn't find that address.";
      }
      result.replaceChildren(el("p", { class: "inline-error", text: message }));
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
    backLink("Use a zip code instead", "#/"),
    heading("h1", "Your street address"),
    el("p", { class: "lead",
              text: "Your address pins down exactly which districts " +
                    "you vote in." }),
    el("form", {
      class: "box", novalidate: "novalidate",
      onsubmit: (event) => { event.preventDefault(); go(); },
    }, [
      el("label", { for: "address", text: "Street, city and zip" }),
      input,
      result,
      el("div", { class: "btn-row" }, [submit]),
    ]),
    el("p", { class: "small muted",
              text: "We look it up with the US Census Bureau's geocoder, " +
                    "which finds the point on the map it falls on." }),
  ]));
  input.focus();
}

async function renderZip(zip) {
  const token = routeToken;
  app.appendChild(loading(`Looking up ${zip}...`));
  const { ok, status, body } = await getJson(`/api/zip/${zip}`);
  if (isStale(token)) return;
  app.innerHTML = "";
  if (!ok) {
    if (status === 0) {
      app.appendChild(offlineNotice());
    } else if (status === 404) {
      app.appendChild(notice(`No district data for ${zip}`,
        "We don't have this zip code's districts. Check the number, " +
        "or look up your street address instead.", homeActions()));
    } else {
      app.appendChild(notice("We couldn't look up that zip code",
        body && body.error ? `The lookup said: ${body.error}.` :
          "Something went wrong on our side. Try again in a moment.",
        homeActions()));
    }
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
    // Replace, so Back from the ballot returns home, not to a page
    // that would forward straight back here.
    location.replace(`#/ballot?${params}`);
    return;
  }
  await renderAmbiguousKind(zip, body, body.ambiguous[0]);
}

const KIND_NAMES = {
  cd: "congressional district",
  sldu: "State Senate district",
  sldl: "State Assembly district",
  county: "county",
};

async function renderAmbiguousKind(zip, zipDoc, kind) {
  app.innerHTML = "";
  window.scrollTo(0, 0);
  const kindName = KIND_NAMES[kind] || "district";
  const entries = zipDoc.kinds[kind];
  const letters = {};
  entries.forEach((entry, i) => { letters[entry.ocd_id] = letterFor(i); });

  const mapDiv = el("div", { class: "map-container",
                             "aria-label": `Map of the ${kindName}s in ${zip}` });
  const list = el("ul", { class: "choice-list" });
  for (const entry of entries) {
    list.appendChild(el("li", {}, [
      el("button", {
        type: "button", class: "box choice",
        onclick: () => selectDistrict(zip, zipDoc, kind, entry.ocd_id),
      }, [
        el("span", { class: "district-letter", text: letters[entry.ocd_id] }),
        el("span", { class: "choice-name", text: entry.name }),
        el("span", { class: "chev", "aria-hidden": "true", text: "›" }),
      ]),
    ]));
  }
  const more = zipDoc.ambiguous.length - 1;
  app.appendChild(el("section", {}, [
    backLink("Change zip code", "#/"),
    heading("h1", `Which ${kindName} are you in?`),
    el("p", {}, [
      `Zip code ${zip} is split between ${entries.length} ${kindName}s. ` +
      "Tap yours on the map or in the list.",
      more > 0 ? ` Then ${more === 1 ? "one more question" :
        `${more} more questions`}.` : null,
    ]),
    mapDiv,
    el("p", { class: "map-note",
              text: "The dotted line is your zip code. Each district " +
                    "carries its letter." }),
    list,
    el("p", { class: "muted" }, [
      "Not sure which? ",
      el("a", { href: "#/address", text: "Look up your street address" }),
      " and we'll work it out.",
    ]),
  ]));
  const { body: shapes } = await getJson(
    `/api/zip/${zip}/shapes?kind=${encodeURIComponent(kind)}`);
  if (shapes && shapes.features && mapDiv.isConnected) {
    drawMap(mapDiv, shapes,
      (ocdId) => selectDistrict(zip, zipDoc, kind, ocdId), letters);
  } else {
    mapDiv.remove();
  }
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

// "ca-2026-11-03" -> "Tuesday, November 3, 2026".
function electionDate(electionId) {
  const m = /(\d{4})-(\d{2})-(\d{2})$/.exec(electionId || "");
  if (!m) return null;
  const date = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return date.toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric", year: "numeric",
    timeZone: "UTC",
  });
}

// Splits "Proposition 2: Increases ..." into a short name to lead with
// and the rest; a measure without one is led by its number.
function titleParts(contest) {
  const m = /^((?:Proposition|Measure|Prop\.?)\s+[^:]+):\s*(.+)$/.exec(
    contest.title);
  if (m) return { eyebrow: m[1], title: m[2] };
  if (contest.kind === "measure" && contest.number &&
      !contest.title.includes(contest.number)) {
    return { eyebrow: `Measure ${contest.number}`, title: contest.title };
  }
  return { eyebrow: null, title: contest.title };
}

function contestHeading(contest) {
  const { eyebrow, title } = titleParts(contest);
  if (!eyebrow) {
    return [el("h3", { class: "contest-eyebrow contest-title-only",
                       text: title })];
  }
  return [el("h3", { class: "contest-eyebrow", text: eyebrow }),
          el("p", { class: "contest-title", text: title })];
}

// The ballot list does not carry poster URLs; a local video's poster
// sits beside it, so it is tried there and dropped if it isn't.
function posterFor(videoUrl) {
  if (!videoUrl || !/\/video\.mp4$/.test(videoUrl)) return null;
  return videoUrl.replace(/video\.mp4$/, "poster.jpg");
}

async function renderBallot(divisions, matchedAddress) {
  app.appendChild(loading("Getting your ballot..."));
  const token = routeToken;
  const query = divisions.map((d) => `d=${encodeURIComponent(d)}`).join("&");
  const { ok, status, body } = await getJson(`/api/ballot?${query}`);
  if (isStale(token)) return;
  app.innerHTML = "";
  if (!ok) {
    app.appendChild(status === 0 ? offlineNotice() :
      notice("We couldn't load your ballot",
        "Something went wrong on our side. Try again in a moment, or " +
        "start over with your zip code.",
        [button("Try again", { class: "btn btn-primary", onclick: route }),
         linkButton("Start over", "#/", "btn-quiet")]));
    return;
  }
  // The contest page's back link returns to this ballot.
  try {
    sessionStorage.setItem("ballotreels.ballot", location.hash);
  } catch (e) { /* private mode: the back link falls back to home */ }

  const contests = body.levels.flatMap((level) => level.contests);
  const ready = contests.filter((c) => c.status === "cached").length;
  const when = electionDate(body.election);
  const section = el("section", {}, [
    backLink("Change zip code", "#/"),
    heading("h1", "Your ballot"),
    when ? el("p", { class: "muted", text: `Election day: ${when}` }) : null,
  ]);
  if (matchedAddress) {
    section.appendChild(el("p", { class: "box matched" }, [
      el("span", { text: `Matched address: ${matchedAddress}. ` }),
      el("a", { href: "#/address", text: "Not your address? Try again" }),
    ]));
  }
  if (contests.length === 0) {
    section.appendChild(notice("Nothing on this ballot yet",
      "We don't have any contests for these districts yet. Check back " +
      "closer to election day.", homeActions()));
    app.appendChild(section);
    return;
  }
  section.appendChild(el("p", {
    text: `${contests.length} ${contests.length === 1 ? "contest" : "contests"}` +
      ` · ${ready} ${ready === 1 ? "video" : "videos"} ready to watch`,
  }));
  for (const level of body.levels) {
    section.appendChild(el("h2", { class: "level-heading",
                                   text: LEVEL_NAMES[level.level] || level.level }));
    for (const contest of level.contests) {
      section.appendChild(renderContestCard(contest));
    }
  }
  app.appendChild(section);
}

function renderContestCard(contest) {
  if (contest.status === "unavailable") {
    return el("div", { class: "box contest inert", "aria-disabled": "true" }, [
      el("div", { class: "contest-body" }, [
        ...contestHeading(contest),
        el("p", { class: "inert-note",
                  text: contest.kind === "race" ?
                    "No video: candidate races aren't covered yet." :
                    "No video for this one yet." }),
      ]),
    ]);
  }
  if (contest.status === "cached") {
    const poster = posterFor(contest.video_url);
    let thumb;
    if (poster) {
      thumb = el("img", { class: "thumb", src: poster, alt: "",
                          loading: "lazy" });
      thumb.addEventListener("error", () => {
        thumb.replaceWith(el("span", { class: "thumb thumb-blank" },
                             [icon("play")]));
      });
    } else {
      thumb = el("span", { class: "thumb thumb-blank" }, [icon("play")]);
    }
    return el("a", { class: "box contest", href: `#/contest/${contest.id}` }, [
      thumb,
      el("div", { class: "contest-body" }, [
        ...contestHeading(contest),
        el("span", { class: "btn btn-primary" }, [icon("play"), "Watch"]),
      ]),
    ]);
  }
  const body = el("div", { class: "contest-body" }, contestHeading(contest));
  const card = el("div", { class: "box contest" }, [
    el("span", { class: "thumb thumb-blank" }, [icon("pencil")]),
    body,
  ]);
  const onDone = (job) => card.replaceWith(renderContestCard({
    ...contest, status: "cached", video_url: job.video_url, job: null }));
  if ((contest.status === "queued" || contest.status === "running") &&
      contest.job) {
    const progress = makeProgress(false);
    body.appendChild(progress.node);
    progress.update(contest.job);
    pollJob(contest.id, contest.job.id, progress, onDone);
    return card;
  }
  body.appendChild(generateControls(contest, false, onDone));
  return card;
}

// -- making a video ----------------------------------------------------

// The worker's stages (ballotreels/pipeline.py, then the upload), in
// plain words.
const STAGES = [
  ["sources", "Gathering the sources"],
  ["script", "Writing the script"],
  ["check", "Checking it against our standard"],
  ["narrate", "Recording the narration"],
  ["render", "Drawing the pictures"],
  ["encode", "Putting the video together"],
  ["cache", "Saving it"],
];

function minutes(n) {
  return `${n} ${n === 1 ? "minute" : "minutes"}`;
}

// A live progress view for one job. `full` adds the list of steps (the
// contest page); the ballot's cards show the short form.
function makeProgress(full) {
  const head = el("span", { text: "Starting..." });
  const fill = el("div", { class: "progress-fill" });
  const meta = el("p", { class: "progress-meta" });
  const steps = el("ol", { class: "steps" });
  const node = el("div", { class: "progress", role: "status",
                           "aria-live": "polite" }, [
    el("p", { class: "progress-head" }, [
      el("span", { class: "progress-dot" }), head]),
    el("div", { class: "progress-bar" }, [fill]),
    meta,
    full ? steps : null,
    full ? el("p", { class: "progress-leave",
      text: "You can leave this page: the video keeps being made, and " +
            "it will be here when you come back." }) : null,
  ]);
  const update = (job) => {
    const at = STAGES.findIndex(([name]) => name === job.stage);
    let done = 0;
    if (job.state === "queued") {
      head.textContent = "Waiting its turn";
      const ahead = (job.position || 1) - 1;
      meta.textContent = (ahead === 0 ? "Next in line" :
        `${ahead} ${ahead === 1 ? "video" : "videos"} ahead of it`) +
        (job.eta_minutes != null ?
          ` · ready in about ${minutes(job.eta_minutes)}` : "");
      fill.style.width = "3%";
    } else {
      head.textContent = at >= 0 ? STAGES[at][1] : "Getting started";
      done = Math.max(at, 0);
      meta.textContent = job.eta_minutes != null ?
        `About ${minutes(job.eta_minutes)} to go` : "";
      fill.style.width = `${Math.round(((done + 0.5) / STAGES.length) * 100)}%`;
    }
    if (full) {
      steps.replaceChildren(...STAGES.map(([, words], i) => el("li", {
        class: job.state === "queued" ? "" :
          i < done ? "done" : i === done ? "now" : "",
        text: words,
      })));
    }
  };
  return { node, update };
}

function failureMessage(stage) {
  if (stage === "sources") return "Sources for this contest haven't been archived yet.";
  if (stage === "script") return "Automatic script writing isn't built yet.";
  return "This video couldn't be made. The operator has been notified by the queue.";
}

function failureNode(stage) {
  return el("div", { class: "inline-error", role: "alert" }, [
    el("p", { text: `No video yet. ${failureMessage(stage)}` }),
    el("a", { href: REPORT_URL, text: "Tell us about it" }),
  ]);
}

// The "Make the video" button and what replaces it: the live progress,
// or a message if the queue says no. onStarted, if given, runs once the
// job is queued, before the progress view shows.
function generateControls(contest, full, onDone, onStarted) {
  const wrap = el("div", {});
  const note = el("p", { class: "wait-note",
    text: "No video yet. Making one takes a few minutes." });
  const start = button("Make the video", {
    class: full ? "btn btn-primary btn-block" : "btn btn-primary",
  });
  const message = el("div", { "aria-live": "polite" });
  start.addEventListener("click", async () => {
    start.disabled = true;
    start.textContent = "Starting...";
    message.replaceChildren();
    const { status: httpStatus, body, headers } = await postJson(
      "/api/generate", { contest: contest.id });
    if (body && body.status === "cached") {
      location.hash = `#/contest/${contest.id}`;
      return;
    }
    if (body && body.job) {
      const progress = makeProgress(full);
      if (onStarted) onStarted();
      wrap.replaceChildren(progress.node);
      progress.update(body.job);
      pollJob(contest.id, body.job.id, progress, onDone);
      return;
    }
    start.disabled = false;
    start.textContent = "Make the video";
    let text;
    if (body && (body.status === "failed" || body.status === "cancelled")) {
      text = "This video isn't available yet.";
    } else if (httpStatus === 429 && body && body.limit === "global") {
      text = "Many videos have been requested this hour. Please try " +
        "again later.";
    } else if (httpStatus === 429) {
      const wait = Math.ceil(Number(headers.get("Retry-After")) / 60);
      text = "You've started several videos in a short time. Please try " +
        "again" + (wait > 0 ? ` in about ${minutes(wait)}.` : " later.");
    } else if (httpStatus === 0) {
      text = "We couldn't reach ballotreels. Check your connection and " +
        "try again.";
    } else {
      text = body && body.error ? `That didn't work: ${body.error}.` :
        "That didn't work. Try again in a moment.";
    }
    message.replaceChildren(el("p", { class: "inline-error", text }));
  });
  // The contest page says "No video yet" in its own heading.
  wrap.append(...(full ? [] : [note]), start, message);
  return wrap;
}

// Polls one job until it ends, updating its progress view in place. A
// poll stops as soon as its view has left the page (the voter moved on,
// or the ballot re-rendered), so polls never pile up or pull the voter
// to another page.
async function pollJob(contestId, jobId, progress, onDone) {
  const { body } = await getJson(`/api/jobs/${jobId}`);
  if (!progress.node.isConnected) return;
  if (!body) {
    setTimeout(() => pollJob(contestId, jobId, progress, onDone), 8000);
    return;
  }
  if (body.state === "done") {
    onDone(body);
    return;
  }
  if (body.state === "failed") {
    progress.node.replaceWith(failureNode(body.failed_stage));
    return;
  }
  if (body.state !== "queued" && body.state !== "running") {
    progress.node.replaceWith(el("p", { class: "wait-note",
      text: "This video was stopped before it was finished, so it " +
            "isn't available yet." }));
    return;
  }
  progress.update(body);
  setTimeout(() => pollJob(contestId, jobId, progress, onDone), 4000);
}

function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch (e) {
    return "";
  }
}

// The video is the contest page's hero: its frame takes the height left
// below the header, back link and title (which wraps to 1-3 lines), so
// the whole frame, controls included, is on screen without scrolling.
function fitVideo() {
  const frame = app.querySelector(".video-frame:not(.empty)");
  if (!frame) return;
  const top = frame.getBoundingClientRect().top + window.scrollY;
  frame.style.setProperty("--above", `${Math.ceil(top)}px`);
}

window.addEventListener("resize", fitVideo);
// The hand-drawn fonts can land after the page renders and rewrap the
// title, which moves the frame.
if (document.fonts) document.fonts.addEventListener("loadingdone", fitVideo);

async function renderContest(contestId) {
  const token = routeToken;
  app.appendChild(loading("Loading..."));
  const { ok, status, body } = await getJson(`/api/contest/${contestId}`);
  if (isStale(token)) return;
  app.innerHTML = "";
  let ballot = null;
  try {
    ballot = sessionStorage.getItem("ballotreels.ballot");
  } catch (e) { /* no storage: back goes home */ }
  const back = ballot ? backLink("Your ballot", ballot) :
    backLink("Find your ballot", "#/");
  if (!ok) {
    app.appendChild(status === 0 ? offlineNotice() :
      notice("We couldn't find that contest",
        "The link may be old, or the contest may have been renamed.",
        [linkButton(ballot ? "Back to your ballot" : "Find your ballot",
                    ballot || "#/", "btn-primary")]));
    return;
  }
  const { eyebrow, title } = titleParts(body);
  const section = el("section", { class: "contest-page" }, [
    back,
    eyebrow ? el("p", { class: "contest-eyebrow", text: eyebrow }) : null,
    heading("h1", title),
  ]);

  if (body.video_url) {
    const video = el("video", { src: body.video_url, controls: "controls",
                                playsinline: "playsinline",
                                preload: "metadata" });
    if (body.poster_url) video.setAttribute("poster", body.poster_url);
    section.appendChild(el("div", { class: "video-frame" }, [video]));
    // Fitted once the rest of the page is in and laid out below.
    requestAnimationFrame(fitVideo);
  } else {
    const frame = el("div", { class: "video-frame empty" });
    if (body.status === "unavailable") {
      frame.append(el("h2", { text: "Not available yet" }),
        el("p", { text: body.kind === "race" ?
          "Candidate races aren't covered yet. Measures are." :
          "There's no video for this contest yet." }));
    } else if ((body.status === "queued" || body.status === "running") &&
               body.job) {
      const progress = makeProgress(true);
      frame.append(el("h2", { text: "Making the video" }), progress.node);
      progress.update(body.job);
      pollJob(body.id, body.job.id, progress, route);
    } else {
      const title = el("h2", { text: "No video yet" });
      const wait = el("p", { text: "Making one takes a few minutes. " +
                                   "Once it's made, it's here for everyone." });
      // Once started, the frame reads as the page-load generating state.
      frame.append(title, wait, generateControls(body, true, route, () => {
        title.textContent = "Making the video";
        wait.remove();
      }));
    }
    section.appendChild(frame);
  }

  section.appendChild(heading("h2", "Sources", { class: "section-title" }));
  if (body.sources && body.sources.length) {
    const sourceList = el("ol", { class: "sources" });
    for (const source of body.sources) {
      const host = hostOf(source.url);
      sourceList.appendChild(el("li", {}, [
        el("a", { href: source.url, rel: "noopener",
                  text: source.publisher || source.url }),
        host && source.publisher ?
          el("span", { class: "source-host", text: host }) : null,
      ]));
    }
    section.appendChild(sourceList);
  } else {
    section.appendChild(el("p", { class: "muted",
      text: "Every source the video draws on is listed here once it's made." }));
  }

  const corrections = el("div", { class: "scrap corrections" }, [
    el("p", { class: "promise-title", text: "Corrections" }),
  ]);
  if (body.corrections && body.corrections.length) {
    const list = el("ul", {});
    for (const c of body.corrections) {
      list.appendChild(el("li", {}, [
        el("span", { class: "date", text: `${c.date}: ` }), c.note]));
    }
    corrections.appendChild(list);
  } else {
    corrections.appendChild(el("p", { text: "None so far. If a fact is " +
      "wrong or the sides don't get equal time, report it: corrections " +
      "are dated and listed here." }));
  }
  corrections.appendChild(el("p", { class: "report" }, [
    el("a", { class: "btn btn-quiet", href: body.report_url || REPORT_URL,
              text: "Report an error with this video" }),
  ]));
  section.appendChild(corrections);

  section.appendChild(el("p", { class: "fine-print" }, [
    "Made under the ",
    el("a", { href: STANDARD_URL, text: "ballotreels standard" }),
    `, version ${body.standard_version}` +
      (body.template_version != null ?
        ` · template ${body.template_version}` : "") + ".",
  ]));
  app.appendChild(section);
}

// The script tag is the last thing in <body>, so the DOM (and #app) is
// already parsed by the time this runs; only hash changes need a
// listener after the first route().
window.addEventListener("hashchange", route);
route();

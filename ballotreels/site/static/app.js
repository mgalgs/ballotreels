// ballotreels phone UI: a router over the public JSON API, on short
// paths (/ut, /ut/2026/amendment-a) kept in the address bar with the
// History API, so it can be copied and shared. No build step, no
// framework. Map drawing uses Leaflet when it is loaded
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
  fullscreen: '<svg viewBox="0 0 22 22" aria-hidden="true"><path d="M3 8 ' +
    'L3 3 L8 3 M14 3 L19 3 L19 8 M19 14 L19 19 L14 19 M8 19 L3 19 L3 14" ' +
    'fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round"/></svg>',
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
    linkButton("Try another zip", "/", "btn-primary"),
    linkButton("Use my address", "/#/address", "btn-quiet"),
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
     linkButton("Start over", "/", "btn-quiet")]);
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

// The page's route: a hash route (the zip and address flow, which are
// personal and not shared, and every link from before the short paths)
// wins over the path.
function currentRoute() {
  const hash = location.hash.replace(/^#/, "");
  if (hash) {
    const [path, query] = hash.split("?");
    return { path, params: new URLSearchParams(query || ""), hash: true };
  }
  return { path: location.pathname,
           params: new URLSearchParams(location.search), hash: false };
}

// The address bar's URL when route() last ran: a popstate or hashchange
// for the URL already shown (both fire for one hash navigation) is not
// routed again.
let routedHref = null;

// Navigates within the app: a new history entry (or, with `replace`,
// the current one rewritten) and the page for it.
function go(href, replace) {
  if (replace) history.replaceState(null, "", href);
  else history.pushState(null, "", href);
  route();
}

// Shows the short path for the page already on screen (an old link's
// page, once its short path is known).
function showPath(href) {
  if (location.pathname + location.search + location.hash === href) return;
  history.replaceState(null, "", href);
  routedHref = location.href;
}

// Paths the server answers itself: a link to one is a real page load.
const SERVER_PATHS = /^\/(?:api|static|v|admin)(?:\/|$)/;

// Same-site links navigate in the app rather than reloading the page.
// An old-style "#/..." href is taken from the site root, so it never
// lands on top of a short path (/ut#/address).
document.addEventListener("click", (event) => {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey ||
      event.ctrlKey || event.shiftKey || event.altKey) return;
  const link = event.target.closest("a[href]");
  if (!link || link.target || link.hasAttribute("download")) return;
  const raw = link.getAttribute("href");
  const url = new URL(raw.startsWith("#") ? `/${raw}` : raw, location.href);
  if (url.origin !== location.origin || SERVER_PATHS.test(url.pathname)) {
    return;
  }
  event.preventDefault();
  go(url.pathname + url.search + url.hash);
});

// Bumped on every route() call. A render that awaits the server checks
// it afterwards and drops its result if the voter has moved on, so a
// late response never replaces the page they are now on.
let routeToken = 0;

function isStale(token) {
  return token !== routeToken;
}

function notFound() {
  app.appendChild(notice("Page not found",
    "That link doesn't go anywhere on ballotreels.",
    [linkButton("Find your ballot", "/", "btn-primary")]));
}

async function route() {
  routeToken += 1;
  routedHref = location.href;
  const { path, params, hash } = currentRoute();
  app.innerHTML = "";
  window.scrollTo(0, 0);
  document.title = "ballotreels";
  if (path === "/" || path === "") {
    showPath("/");
    return renderHome();
  }
  // A state's page: /ut, its election by year (/ut/2026), and the
  // old /state/ut and #/state/ut, which show as /ut once loaded.
  let m = path.match(/^\/state\/([a-z]{2})$/);
  if (m) return renderState(m[1], null, true);
  m = !hash && path.match(/^\/([a-z]{2})(?:\/(\d{4}))?$/);
  if (m) return renderState(m[1], m[2] || null, false);
  // A measure's page: /ut/2026/amendment-a, and the old #/contest/<id>.
  m = !hash && path.match(/^\/([a-z]{2})\/(\d{4})\/([^/]+)$/);
  if (m) return renderContest(`/api/contest/${m[1]}/${m[2]}/${m[3]}`);
  m = hash && path.match(/^\/contest\/(.+)$/);
  if (m) return renderContest(`/api/contest/${m[1]}`);
  m = hash && path.match(/^\/zip\/([0-9]+)$/);
  if (m) return renderZip(m[1]);
  if (hash && path === "/address") return renderAddress();
  if (hash && path === "/ballot") {
    return renderBallot(params.getAll("d"), params.get("addr"));
  }
  notFound();
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
        go(`/#/zip/${zip}`);
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
    linkButton("Use my street address", "/#/address", "btn-quiet btn-block"),
    el("p", { class: "field-note",
              text: "Pins down your exact districts when a zip code " +
                    "spans more than one." }),
  ]));
  const states = el("ul", { class: "state-list" });
  const browse = el("section", { class: "browse", hidden: "hidden" }, [
    el("h2", { class: "browse-title", text: "Or browse a state's measures" }),
    states,
  ]);
  app.appendChild(browse);
  fillStates(states, browse, routeToken);
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

// The states served, as links to their statewide measures; the section
// stays hidden if the list can't be had.
async function fillStates(list, section, token) {
  const { ok, body } = await getJson("/api/states");
  if (isStale(token) || !ok || !body.states.length) return;
  list.replaceChildren(...body.states.map((s) => el("li", {}, [
    el("a", { class: "btn btn-quiet state-link", href: `/${s.state}`,
              text: s.name.replace(/^the /, "") }),
  ])));
  section.hidden = false;
}

// Where the contest page's back link goes: the ballot or state page
// the voter came from.
function rememberBack(href, label) {
  try {
    sessionStorage.setItem("ballotreels.back",
      JSON.stringify({ href, label }));
  } catch (e) { /* private mode: the back link falls back to home */ }
}

function recalledBack() {
  try {
    const back = JSON.parse(sessionStorage.getItem("ballotreels.back"));
    if (back && back.href && back.label) return back;
  } catch (e) { /* no storage, or nothing stored */ }
  return null;
}

// "ca-2026-11-03" -> "November 3".
function electionDay(electionId) {
  const m = /(\d{4})-(\d{2})-(\d{2})$/.exec(electionId || "");
  if (!m) return "election day";
  return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])).toLocaleDateString(
    "en-US", { month: "long", day: "numeric", timeZone: "UTC" });
}

// A state whose election has nothing on it at all.
function noMeasuresNotice(body, actions) {
  const name = body.state_name.replace(/^the /, "");
  return notice(`No statewide measures in ${name}`,
    `There are no statewide measures on ${name}'s ballot on ` +
    `${electionDay(body.election)}.`, actions);
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
      if (status === 404 && body && body.covered === false) {
        message = body.state_name ?
          `We don't cover ${body.state_name} yet.` :
          "We don't cover that address's state yet.";
      } else if (status === 404) {
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
    go(`/#/ballot?${params}`);
  };
  app.appendChild(el("section", {}, [
    backLink("Use a zip code instead", "/"),
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
    } else if (status === 404 && body && body.covered === false) {
      app.appendChild(notice(body.state_name ?
          `We don't cover ${body.state_name} yet` :
          "We don't cover this zip yet",
        `Zip code ${zip} is outside the states ballotreels covers so far.`,
        [linkButton("Try another zip code", "/", "btn-primary")]));
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
  if (body.needs_address) {
    // A zip across a state line: the street address says which state.
    app.appendChild(notice(`Zip code ${zip} crosses a state line`,
      `It is partly in ${body.states.map((s) => s.name).join(" and ")}. ` +
      "Your street address tells us which ballot is yours.",
      [linkButton("Use my street address", "/#/address", "btn-primary"),
       linkButton("Change zip code", "/", "btn-quiet")]));
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
    go(`/#/ballot?${params}`, true);
    return;
  }
  await renderAmbiguousKind(zip, body, body.ambiguous[0]);
}

const KIND_NAMES = {
  cd: "congressional district",
  county: "county",
};

// What a state calls its legislative chambers comes with the zip and
// ballot answers (`chambers`: { sldu: "State Senate", sldl: ... }).
function kindLabel(kind, chambers) {
  const chamber = (chambers || {})[kind];
  if (chamber) return `${chamber} district`;
  return KIND_NAMES[kind] || "district";
}

async function renderAmbiguousKind(zip, zipDoc, kind) {
  app.innerHTML = "";
  window.scrollTo(0, 0);
  const kindName = kindLabel(kind, zipDoc.chambers);
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
    backLink("Change zip code", "/"),
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
      el("a", { href: "/#/address", text: "Look up your street address" }),
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
  go(`/#/ballot?${params}`);
}

const LEVEL_NAMES = {
  state: "Statewide",
  cd: "Congressional",
  county: "County",
};

function levelName(level, chambers) {
  return (chambers || {})[level] || LEVEL_NAMES[level] || level;
}

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

// A ballot measure's designation, as states write it: "Proposition",
// "Amendment", "Issue", "Question", "Initiative Measure No.",
// "Constitutional Amendment", "Charter Amendment", "Referendum", ...
const DESIGNATION = String.raw`(?:(?:Constitutional|Charter|Legislative|` +
  String.raw`Legislatively\s+Referred|Citizen|Ballot|State)\s+)*` +
  String.raw`(?:Proposition|Proposal|Prop\.?|Measure|Amendment|Issue|` +
  String.raw`Question|Initiative|Referendum)` +
  String.raw`(?:\s+(?:Measure|Petition))?(?:\s+No\.)?`;
// Its number or code: "2", "1A", "HJR 1", "2117", or a letter code
// ("A", "ULT") when a colon or dash follows.
const DESIGNATION_CODE = String.raw`(?:(?:[A-Z]{1,4}[- ]?)?\d+[A-Z]?` +
  String.raw`(?:-\d+)?|[A-Z]{1,8}(?=\s*[:\u2013\u2014]|\s+-\s))`;
const TITLE_RE = new RegExp(
  String.raw`^(${DESIGNATION}\s*${DESIGNATION_CODE})` +
  String.raw`(?:\s*[:\u2013\u2014]\s*|\s+-\s+|\s+)(\S.*)$`);

// Splits "Proposition 2: Increases ..." (or "Amendment 4 - Limits ...",
// "Initiative Measure No. 2117: Concerns ...") into a short name to lead
// with and the rest; a measure without one is led by its number.
function titleParts(contest) {
  const m = TITLE_RE.exec(contest.title);
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
         linkButton("Start over", "/", "btn-quiet")]));
    return;
  }
  // The contest page's back link returns to this ballot.
  rememberBack(`/${location.hash}`, "Your ballot");

  const contests = body.levels.flatMap((level) => level.contests);
  const ready = contests.filter((c) => c.status === "cached").length;
  const when = electionDate(body.election);
  const section = el("section", {}, [
    backLink("Change zip code", "/"),
    heading("h1", "Your ballot"),
    when ? el("p", { class: "muted", text: `Election day: ${when}` }) : null,
  ]);
  if (matchedAddress) {
    section.appendChild(el("p", { class: "box matched" }, [
      el("span", { text: `Matched address: ${matchedAddress}. ` }),
      el("a", { href: "/#/address", text: "Not your address? Try again" }),
    ]));
  }
  if (contests.length === 0 && body.empty_election) {
    section.appendChild(noMeasuresNotice(body, [
      linkButton("Try another zip", "/", "btn-primary")]));
    app.appendChild(section);
    return;
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
                                   text: levelName(level.level, body.chambers) }));
    for (const contest of level.contests) {
      section.appendChild(renderContestCard(contest));
    }
  }
  app.appendChild(section);
}

// `year`, if given, must be the year of the state's election; `old`: an
// old link, which shows as the short path once the page is in.
async function renderState(abbr, year, old) {
  app.appendChild(loading("Getting the measures..."));
  const token = routeToken;
  const { ok, status, body } = await getJson(`/api/state/${abbr}`);
  if (isStale(token)) return;
  app.innerHTML = "";
  if (!ok) {
    if (status === 0) {
      app.appendChild(offlineNotice());
    } else if (status === 404) {
      app.appendChild(notice(body && body.state_name ?
          `We don't cover ${body.state_name} yet` :
          "We don't cover that state yet",
        "ballotreels doesn't have this state's ballot so far.",
        [linkButton("Find your ballot", "/", "btn-primary")]));
    } else {
      app.appendChild(notice("We couldn't load these measures",
        "Something went wrong on our side. Try again in a moment.",
        [button("Try again", { class: "btn btn-primary", onclick: route }),
         linkButton("Start over", "/", "btn-quiet")]));
    }
    return;
  }
  if (year && body.year !== year) {
    notFound();
    return;
  }
  if (old) showPath(`/${body.state}`);
  const name = body.state_name.replace(/^the /, "");
  document.title = `${name} measures · ballotreels`;
  rememberBack(location.pathname, `${name} measures`);
  const contests = body.levels.flatMap((level) => level.contests);
  const ready = contests.filter((c) => c.status === "cached").length;
  const when = electionDate(body.election);
  const section = el("section", {}, [
    backLink("Find your ballot", "/"),
    heading("h1", `${name} statewide measures`),
    when ? el("p", { class: "muted", text: `Election day: ${when}` }) : null,
  ]);
  if (contests.length === 0) {
    section.appendChild(noMeasuresNotice(body, [
      linkButton("Find your ballot", "/", "btn-primary")]));
    app.appendChild(section);
    return;
  }
  section.appendChild(el("p", {
    text: `${contests.length} ${contests.length === 1 ? "measure" : "measures"}` +
      ` · ${ready} ${ready === 1 ? "video" : "videos"} ready to watch`,
  }));
  for (const contest of contests) {
    section.appendChild(renderContestCard(contest));
  }
  section.appendChild(el("p", { class: "muted small" }, [
    "Your own ballot may also have district and county measures. ",
    el("a", { href: "/", text: "Find it by zip code" }),
    ".",
  ]));
  app.appendChild(section);
}

// A contest the public can't start a video for: a race, or one whose
// latest video was stopped or couldn't be made (only the operator
// retries those).
const UNAVAILABLE_STATES = ["unavailable", "failed", "cancelled"];

function unavailableNote(contest) {
  if (contest.kind === "race") {
    return "No video: candidate races aren't covered yet.";
  }
  return contest.status === "unavailable" ? "No video for this one yet." :
    "This video isn't available yet.";
}

function renderContestCard(contest) {
  if (UNAVAILABLE_STATES.includes(contest.status)) {
    return el("div", { class: "box contest inert", "aria-disabled": "true" }, [
      el("div", { class: "contest-body" }, [
        ...contestHeading(contest),
        el("p", { class: "inert-note", text: unavailableNote(contest) }),
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
    return el("a", { class: "box contest", href: contest.path }, [
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
  if (LIVE_STATES.includes(contest.status) && contest.job) {
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

// A job that is on its way: "pending" (requested, waiting for the
// operator's review), "queued" or "running".
const LIVE_STATES = ["pending", "queued", "running"];

// The contest page's heading over a live job's progress.
function liveHeading(job) {
  return job.state === "pending" ? "Video requested" : "Making the video";
}

function minutes(n) {
  return `${n} ${n === 1 ? "minute" : "minutes"}`;
}

// A live progress view for one job. `full` adds the list of steps (the
// contest page); the ballot's cards show the short form. `title`, if
// given, is a heading kept in step with the job's state.
function makeProgress(full, title) {
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
    if (title) title.textContent = liveHeading(job);
    if (job.state === "pending") {
      // No ETA: nothing is made until someone has reviewed the request.
      head.textContent = "Requested: waiting for review";
      meta.textContent = "Someone checks each request before the video " +
        "is made.";
      fill.style.width = "0%";
    } else if (job.state === "queued") {
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
        class: job.state !== "running" ? "" :
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
// job is queued, before the progress view shows; `title`, if given, is
// the heading the progress view keeps in step with the job's state.
function generateControls(contest, full, onDone, onStarted, title) {
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
      go(contest.path);
      return;
    }
    if (body && body.job) {
      const progress = makeProgress(full, title);
      if (onStarted) onStarted(body.job);
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
  if (!LIVE_STATES.includes(body.state)) {
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
// On a wide screen the frame sits beside the page's text, at the top of
// the contest section, and sticks while the text scrolls; a stuck
// frame's own box has moved, so the section's top is measured there.
function fitVideo() {
  const frame = app.querySelector(".video-frame:not(.empty)");
  if (!frame) return;
  const placed = getComputedStyle(frame).position === "sticky" ?
    frame.parentElement : frame;
  const top = placed.getBoundingClientRect().top + window.scrollY;
  frame.style.setProperty("--above", `${Math.ceil(top)}px`);
}

window.addEventListener("resize", fitVideo);
// The hand-drawn fonts can land after the page renders and rewrap the
// title, which moves the frame.
if (document.fonts) document.fonts.addEventListener("loadingdone", fitVideo);

// -- the video and its full-screen button ------------------------------

// iPhone Safari has no requestFullscreen for a <video>, only its own
// webkitEnterFullscreen; elsewhere the standard call (or its webkit
// prefix, older desktop Safari).
function enterFullscreen(video) {
  if (video.requestFullscreen) {
    const done = video.requestFullscreen();
    if (done && done.catch) {
      done.catch(() => {
        if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();
      });
    }
  } else if (video.webkitEnterFullscreen) {
    video.webkitEnterFullscreen();
  } else if (video.webkitRequestFullscreen) {
    video.webkitRequestFullscreen();
  }
}

// The contest page's video frame and the full-screen button under it;
// nothing when there is no video yet.
function videoNodes(body) {
  if (!body.video_url) return [];
  const video = el("video", { src: body.video_url, controls: "controls",
                              playsinline: "playsinline",
                              preload: "metadata" });
  if (body.poster_url) video.setAttribute("poster", body.poster_url);
  const full = el("button", {
    type: "button", class: "btn btn-quiet fullscreen-btn",
    onclick: () => enterFullscreen(video),
  }, [icon("fullscreen"), "Full screen"]);
  return [el("div", { class: "video-frame has-fullscreen" }, [video]),
          el("div", { class: "fullscreen-row" }, [full])];
}

// -- chapters: a chip per section of the video -------------------------

// "m:ss", or "h:mm:ss.mmm" for WebVTT.
function clock(seconds) {
  const s = Math.floor(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function vttTime(seconds) {
  const ms = Math.round(seconds * 1000);
  const pad = (n, w) => String(n).padStart(w, "0");
  return `${pad(Math.floor(ms / 3600000), 2)}:` +
    `${pad(Math.floor(ms / 60000) % 60, 2)}:` +
    `${pad(Math.floor(ms / 1000) % 60, 2)}.${pad(ms % 1000, 3)}`;
}

// The chapters as a WebVTT file: each runs until the next starts, the
// last to the end of the video (or, before its length is known, far
// past it).
function chaptersVtt(chapters, duration) {
  const end = isFinite(duration) && duration > 0 ? duration : 359999;
  const cues = chapters.map((c, i) => {
    const next = i + 1 < chapters.length ? chapters[i + 1].start : end;
    return `${i + 1}\n${vttTime(c.start)} --> ` +
      `${vttTime(Math.max(next, c.start))}\n` +
      c.title.replace(/-->/g, "->").replace(/\s*\n\s*/g, " ");
  });
  return "WEBVTT\n\n" + cues.join("\n\n") + "\n";
}

// The chapter the playhead is in: the last one started by time `t`.
function chapterAt(chapters, t) {
  let at = -1;
  chapters.forEach((c, i) => { if (t + 0.001 >= c.start) at = i; });
  return at;
}

// The chapter chips for `video` (the contest's `chapters`: each
// section's start and heading), and its kind="chapters" track; nothing
// for a video made before chapters were recorded. Every chip is drawn
// the same, whichever side's section it is (STANDARD rule 7.4); the only
// one ever marked is the one the playhead is in, once the video has
// started.
function chapterNodes(chapters, video) {
  if (!chapters || !chapters.length) return [];
  const url = URL.createObjectURL(new Blob([chaptersVtt(chapters)],
                                           { type: "text/vtt" }));
  video.appendChild(el("track", { kind: "chapters", label: "Chapters",
                                  srclang: "en", src: url, default: "" }));
  const chips = chapters.map((c) => el("button", {
    type: "button", class: "chapter-chip",
    onclick: () => {
      video.currentTime = c.start;
      const playing = video.play();
      if (playing && playing.catch) playing.catch(() => {});
    },
  }, [el("span", { class: "chapter-time", text: clock(c.start) }),
      el("span", { class: "chapter-title", text: c.title })]));
  const mark = () => {
    const started = !video.paused || video.currentTime > 0;
    const at = started ? chapterAt(chapters, video.currentTime) : -1;
    chips.forEach((chip, i) => {
      if (i === at) chip.setAttribute("aria-current", "true");
      else chip.removeAttribute("aria-current");
    });
  };
  for (const type of ["timeupdate", "seeked", "play"]) {
    video.addEventListener(type, mark);
  }
  return [el("nav", { class: "chapters", "aria-label": "Chapters" }, [
    el("p", { class: "chapters-title", text: "Jump to a part" }),
    el("ol", {}, chips.map((chip) => el("li", {}, [chip]))),
  ])];
}

// `apiPath`: the contest's API URL, by short path or (an old link) by id.
async function renderContest(apiPath) {
  const token = routeToken;
  app.appendChild(loading("Loading..."));
  const { ok, status, body } = await getJson(apiPath);
  if (isStale(token)) return;
  app.innerHTML = "";
  const recalled = recalledBack();
  const back = recalled ? backLink(recalled.label, recalled.href) :
    backLink("Find your ballot", "/");
  if (!ok) {
    app.appendChild(status === 0 ? offlineNotice() :
      notice("We couldn't find that contest",
        "The link may be old, or the contest may have been renamed.",
        [linkButton(recalled ? `Back to ${recalled.label}` :
                      "Find your ballot",
                    recalled ? recalled.href : "/", "btn-primary")]));
    return;
  }
  showPath(body.path);
  const { eyebrow, title } = titleParts(body);
  document.title = `${eyebrow ? `${eyebrow}: ` : ""}${title} · ballotreels`;
  // The head and the rest are wrapped only for the wide-screen grid,
  // which puts the video in a column of its own beside them; on a phone
  // the wrappers are plain blocks and the page reads top to bottom.
  const section = el("section", {
    class: body.video_url ? "contest-page has-video" : "contest-page",
  }, [
    el("div", { class: "contest-head" }, [
      back,
      eyebrow ? el("p", { class: "contest-eyebrow", text: eyebrow }) : null,
      heading("h1", title),
    ]),
  ]);

  let chapters = [];
  if (body.video_url) {
    const nodes = videoNodes(body);
    section.append(...nodes);
    chapters = chapterNodes(body.chapters, nodes[0].querySelector("video"));
    // Fitted once the rest of the page is in and laid out below.
    requestAnimationFrame(fitVideo);
  } else {
    const frame = el("div", { class: "video-frame empty" });
    if (body.status === "unavailable") {
      frame.append(el("h2", { text: "Not available yet" }),
        el("p", { text: body.kind === "race" ?
          "Candidate races aren't covered yet. Measures are." :
          "There's no video for this contest yet." }));
    } else if (UNAVAILABLE_STATES.includes(body.status)) {
      // Failed or cancelled: only the operator can start it again.
      frame.append(el("h2", { text: "Not available yet" }),
        el("p", { text: "This video isn't available yet." }),
        el("a", { href: body.report_url || REPORT_URL,
                  text: "Tell us about it" }));
    } else if (LIVE_STATES.includes(body.status) && body.job) {
      const title = el("h2", { text: liveHeading(body.job) });
      const progress = makeProgress(true, title);
      frame.append(title, progress.node);
      progress.update(body.job);
      pollJob(body.id, body.job.id, progress, route);
    } else {
      const title = el("h2", { text: "No video yet" });
      const wait = el("p", { text: "Making one takes a few minutes. " +
                                   "Once it's made, it's here for everyone." });
      // Once started, the frame reads as the page-load generating state.
      frame.append(title, wait, generateControls(body, true, route, () => {
        wait.remove();
      }, title));
    }
    section.appendChild(frame);
  }

  // Under the video on a phone; at the top of the text column beside it
  // on a wide screen.
  const rest = el("div", { class: "contest-rest" }, chapters);
  section.appendChild(rest);
  rest.appendChild(heading("h2", "Sources", { class: "section-title" }));
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
    rest.appendChild(sourceList);
  } else {
    rest.appendChild(el("p", { class: "muted",
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
    // a choice question has no sides: its options are treated alike
    const unequal = body.choice ? "the choices aren't treated alike"
                             : "the sides don't get equal time";
    corrections.appendChild(el("p", { text: "None so far. If a fact is " +
      `wrong or ${unequal}, report it: corrections ` +
      "are dated and listed here." }));
  }
  corrections.appendChild(el("p", { class: "report" }, [
    el("a", { class: "btn btn-quiet", href: body.report_url || REPORT_URL,
              text: "Report an error with this video" }),
  ]));
  rest.appendChild(corrections);

  rest.appendChild(el("p", { class: "fine-print" }, [
    "Made under the ",
    el("a", { href: STANDARD_URL, text: "ballotreels standard" }),
    `, version ${body.standard_version}` +
      (body.template_version != null ?
        ` · template ${body.template_version}` : "") + ".",
  ]));
  app.appendChild(section);
}

// The script tag is the last thing in <body>, so the DOM (and #app) is
// already parsed by the time this runs; after the first route(), only
// Back, Forward and a hash typed into the address bar need a listener.
function onHistory() {
  if (location.href !== routedHref) route();
}
window.addEventListener("popstate", onHistory);
window.addEventListener("hashchange", onHistory);
route();

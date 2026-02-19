<script setup>
import { computed, onMounted, ref } from "vue";
import * as d3 from "d3";
import { api } from "../api";

const host = ref(null);
const status = ref("Loading your network…");

const me = ref(null);
const connections = ref([]);
const users = ref([]);
const connectionsLoading = ref(false);
const usersLoading = ref(false);
const graphLoading = ref(false);

const addSlug = ref("");
const addFullName = ref("");
const addLoading = ref(false);
const addError = ref("");
const addSuccess = ref("");
const listError = ref("");
const usersError = ref("");
const graphError = ref("");

const mySlug = ref("");
const claimLoading = ref(false);
const claimError = ref("");
const claimSuccess = ref("");

function normalizeLinkedInSlug(input) {
  const raw = String(input ?? "").trim();
  if (!raw) return "";

  // Common user inputs:
  // - "janedoe"
  // - "linkedin.com/in/janedoe" (no scheme)
  // - "https://www.linkedin.com/in/janedoe/?trk=..."
  // - "/in/janedoe" / "in/janedoe"
  const s0 = raw.replace(/^@/, "");

  const safeDecode = (v) => {
    try {
      return decodeURIComponent(v);
    } catch {
      return v;
    }
  };

  const stripDecorations = (v) =>
    v
      .trim()
      .replace(/^<|>$/g, "")
      .replace(/\s+/g, "")
      .replace(/[?#].*$/, "")
      .replace(/\/+$/, "");

  const s = stripDecorations(s0);

  // If it looks like a LinkedIn URL (with or without scheme), parse it.
  const looksLikeLinkedInHost = /^https?:\/\//i.test(s)
    ? /linkedin\.com/i.test(s)
    : /(^|\b)(www\.)?linkedin\.com\b/i.test(s);

  if (looksLikeLinkedInHost) {
    const withScheme = /^https?:\/\//i.test(s) ? s : `https://${s}`;
    try {
      const url = new URL(withScheme);
      const parts = url.pathname.split("/").filter(Boolean);
      const idx = parts.findIndex((p) => ["in", "pub"].includes(String(p).toLowerCase()));
      if (idx >= 0 && parts[idx + 1]) return safeDecode(parts[idx + 1]).toLowerCase();
      if (parts[0] && !["in", "pub"].includes(String(parts[0]).toLowerCase())) {
        // Last-chance: if user pasted some odd LinkedIn path, take the last segment.
        return safeDecode(parts[parts.length - 1]).toLowerCase();
      }
    } catch {
      // fall through to regex
    }
  }

  // Handle path-like inputs: "/in/janedoe" or "in/janedoe" or "linkedin.com/in/janedoe" (without scheme)
  const m = s.match(/(?:^|\/)(?:in|pub)\/([^/?#]+)/i);
  if (m?.[1]) return safeDecode(m[1]).toLowerCase();

  // If it still looks like LinkedIn but we couldn't extract a profile identifier, don't treat it as a slug.
  if (/linkedin\.com/i.test(s)) return "";

  // Otherwise treat as a slug, stripping any accidental path/query bits.
  return safeDecode(stripDecorations(s)).toLowerCase();
}

const normalizedMySlug = computed(() => normalizeLinkedInSlug(mySlug.value));
const canClaim = computed(() => normalizedMySlug.value.length > 0 && !claimLoading.value);

const normalizedSlug = computed(() => normalizeLinkedInSlug(addSlug.value));
const canSubmit = computed(() => normalizedSlug.value.length > 0 && !addLoading.value);

const searchName = ref("");
const selectedUserId = ref("");
const searchLoading = ref(false);
const searchError = ref("");
const searchResult = ref(null); // { degrees, path }

const graphState = ref(null); // { nodes, edges, nodeSel, linkSel, labelSel }

const normalizedSearch = computed(() => searchName.value.trim().toLowerCase());
const searchMatches = computed(() => {
  const q = normalizedSearch.value;
  if (!q) return [];
  return users.value
    .filter((u) => (u.full_name || "").toLowerCase().includes(q))
    .slice(0, 8);
});

function linkedinUrl(slug) {
  const s = normalizeLinkedInSlug(slug);
  if (!s) return "";
  return `https://www.linkedin.com/in/${encodeURIComponent(s)}/`;
}

function nodeDisplayLabel(d) {
  const label = String(d?.label ?? "").trim();
  const normalizedSlug = normalizeLinkedInSlug(d?.linkedin_slug);
  const url = linkedinUrl(d?.linkedin_slug);

  // For normal user nodes, `label` is the full name already.
  if (d?.type !== "ghost") return label || url || "";

  // For ghost nodes, backend may set `label` to either full_name OR raw slug.
  // If it looks like we're holding only the slug, prefer showing the full URL.
  const looksLikeJustSlug = !!normalizedSlug && label.toLowerCase() === normalizedSlug;
  const looksLikeLinkedInUrl = /linkedin\.com/i.test(label);

  if (label && !looksLikeJustSlug && !looksLikeLinkedInUrl) return label;
  return url || label || "";
}

function edgeKey(a, b) {
  const sa = String(a);
  const sb = String(b);
  return sa < sb ? `${sa}--${sb}` : `${sb}--${sa}`;
}

function clearHighlight() {
  searchResult.value = null;
  searchError.value = "";
  selectedUserId.value = "";
  if (!graphState.value) return;
  const { linkSel, nodeSel, labelSel } = graphState.value;
  linkSel
    .attr("stroke-width", 2)
    .attr("stroke-opacity", 0.6)
    .attr("stroke", "#888");
  nodeSel
    .attr("stroke", "#fff")
    .attr("stroke-width", 2)
    .attr("opacity", 1);
  labelSel
    .attr("font-weight", 400)
    .attr("opacity", 1);
}

function applyHighlight(path) {
  if (!graphState.value) return;
  const pathIds = Array.isArray(path) ? path.map((p) => p.id) : [];
  if (pathIds.length === 0) {
    clearHighlight();
    return;
  }

  const nodeSet = new Set(pathIds.map(String));
  const edgeSet = new Set();
  for (let i = 0; i < pathIds.length - 1; i += 1) {
    edgeSet.add(edgeKey(pathIds[i], pathIds[i + 1]));
  }

  const { linkSel, nodeSel, labelSel } = graphState.value;
  linkSel
    .attr("stroke", (d) => {
      const s = typeof d.source === "object" ? d.source.id : d.source;
      const t = typeof d.target === "object" ? d.target.id : d.target;
      return d.type === "connection" && edgeSet.has(edgeKey(s, t)) ? "#4f8cff" : "#888";
    })
    .attr("stroke-width", (d) => {
      const s = typeof d.source === "object" ? d.source.id : d.source;
      const t = typeof d.target === "object" ? d.target.id : d.target;
      return d.type === "connection" && edgeSet.has(edgeKey(s, t)) ? 5 : 2;
    })
    .attr("stroke-opacity", (d) => {
      const s = typeof d.source === "object" ? d.source.id : d.source;
      const t = typeof d.target === "object" ? d.target.id : d.target;
      return d.type === "connection" && edgeSet.has(edgeKey(s, t)) ? 1 : 0.2;
    });

  nodeSel
    .attr("opacity", (d) => (nodeSet.has(String(d.id)) ? 1 : 0.25))
    .attr("stroke", (d) => (nodeSet.has(String(d.id)) ? "#4f8cff" : "#fff"))
    .attr("stroke-width", (d) => (nodeSet.has(String(d.id)) ? 4 : 2));

  labelSel
    .attr("opacity", (d) => (nodeSet.has(String(d.id)) ? 1 : 0.25))
    .attr("font-weight", (d) => (nodeSet.has(String(d.id)) ? 700 : 400));
}

function renderGraph({ nodes, edges }) {
  host.value.innerHTML = "";

  const width = 1200;
  const height = 600;

  const svg = d3
    .select(host.value)
    .append("svg")
    .attr("width", "100%")
    .attr("height", height)
    .attr("viewBox", `0 0 ${width} ${height}`)
    .call(
      d3.zoom().on("zoom", (event) => {
        g.attr("transform", event.transform);
      })
    );

  const g = svg.append("g");

  const links = edges.map((e) => ({ ...e }));
  const n = nodes.map((d) => ({ ...d }));

  const sim = d3
    .forceSimulation(n)
    .force("link", d3.forceLink(links).id((d) => d.id).distance(90))
    .force("charge", d3.forceManyBody().strength(-250))
    .force("center", d3.forceCenter(width / 2, height / 2));

  const link = g
    .append("g")
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("stroke-width", 2)
    .attr("stroke-opacity", 0.6)
    .attr("stroke", "#888");

  const node = g
    .append("g")
    .selectAll("circle")
    .data(n)
    .join("circle")
    .attr("r", (d) => (d.type === "ghost" ? 8 : 12))
    .attr("fill", (d) => (d.type === "ghost" ? "#aaa" : "#4f8cff"))
    .attr("stroke", "#fff")
    .attr("stroke-width", 2)
    .style("cursor", (d) => (normalizeLinkedInSlug(d.linkedin_slug) ? "pointer" : "default"))
    .on("click", (event, d) => {
      const url = linkedinUrl(d.linkedin_slug);
      if (url) window.open(url, "_blank", "noopener,noreferrer");
    })
    .call(
      d3
        .drag()
        .on("start", (event, d) => {
          if (!event.active) sim.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event, d) => {
          if (!event.active) sim.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
    );

  node.append("title").text((d) => nodeDisplayLabel(d));

  // Add labels
  const labels = g.append("g")
    .selectAll("text")
    .data(n)
    .join("text")
    .attr("font-size", 13)
    .attr("fill", "#222")
    .attr("text-anchor", "middle")
    .attr("dy", 18)
    .text((d) => nodeDisplayLabel(d));

  graphState.value = {
    nodes: n,
    edges: links,
    nodeSel: node,
    linkSel: link,
    labelSel: labels,
  };

  sim.on("tick", () => {
    link
      .attr("x1", (d) => d.source.x)
      .attr("y1", (d) => d.source.y)
      .attr("x2", (d) => d.target.x)
      .attr("y2", (d) => d.target.y);

    node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);

    labels.attr("x", (d) => d.x).attr("y", (d) => d.y);
  });
}

async function runSearch(userId) {
  searchError.value = "";
  searchResult.value = null;
  if (!userId) return;

  searchLoading.value = true;
  try {
    const res = await api.searchPathByUserId(userId);
    searchResult.value = res;
    applyHighlight(res?.path || []);
  } catch (e) {
    searchError.value = e?.message || "Search failed";
    clearHighlight();
  } finally {
    searchLoading.value = false;
  }
}

function selectMatch(u) {
  if (!u?.id) return;
  selectedUserId.value = u.id;
  searchName.value = u.full_name || "";
  runSearch(u.id);
}

async function loadConnections() {
  listError.value = "";
  connectionsLoading.value = true;
  try {
    const data = await api.connectionsList();
    connections.value = Array.isArray(data) ? data : [];
  } catch (e) {
    listError.value = e?.message || "Failed to load connections";
  } finally {
    connectionsLoading.value = false;
  }
}

async function loadUsers() {
  usersError.value = "";
  usersLoading.value = true;
  try {
    const data = await api.usersList();
    users.value = Array.isArray(data) ? data : [];
  } catch (e) {
    usersError.value = e?.message || "Failed to load users";
  } finally {
    usersLoading.value = false;
  }
}

async function loadGraph() {
  graphError.value = "";
  graphLoading.value = true;
  try {
    const data = await api.graphAll();
    renderGraph(data);
    if (searchResult.value?.path?.length) applyHighlight(searchResult.value.path);
  } catch (e) {
    graphError.value = e?.message || "Failed to load graph";
  } finally {
    graphLoading.value = false;
  }
}

async function loadMe() {
  try {
    me.value = await api.me();
    if (!mySlug.value && me.value?.linkedin_slug) mySlug.value = me.value.linkedin_slug;
  } catch {
    // non-fatal; UI can work without this.
  }
}

async function handleClaimSlug() {
  claimError.value = "";
  claimSuccess.value = "";
  const slug = normalizedMySlug.value;
  if (!slug) return;

  claimLoading.value = true;
  try {
    const res = await api.claimMySlug(slug);
    claimSuccess.value = res?.message ? String(res.message) : "LinkedIn claimed";
    await Promise.all([loadMe(), loadUsers(), loadGraph()]);
  } catch (e) {
    claimError.value = e?.message || "Failed to claim LinkedIn";
  } finally {
    claimLoading.value = false;
  }
}

async function handleAddConnection() {
  addError.value = "";
  addSuccess.value = "";

  const slug = normalizedSlug.value;
  if (!slug) return;

  addLoading.value = true;
  try {
    const res = await api.addConnection({
      linkedin_slug: slug,
      full_name: addFullName.value.trim(),
    });
    addSuccess.value = res?.message ? String(res.message) : "Connection updated";
    addSlug.value = "";
    addFullName.value = "";
    await Promise.all([loadConnections(), loadGraph()]);
  } catch (e) {
    addError.value = e?.message || "Failed to add connection";
  } finally {
    addLoading.value = false;
  }
}

onMounted(async () => {
  status.value = "";
  await Promise.all([loadMe(), loadConnections(), loadUsers(), loadGraph()]);
});
</script>

<template>
  <div class="grid gap-4 lg:grid-cols-[380px_1fr]">
    <section class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm lg:sticky lg:top-19" aria-label="Connections panel">
      <h2 class="text-lg font-bold">Connections</h2>
      <p class="mt-1 text-sm text-gray-600" v-if="me?.full_name">Signed in as <strong>{{ me.full_name }}</strong>.</p>

      <form
        v-if="me && !me.linkedin_slug"
        class="mt-4 space-y-3 rounded-xl border border-amber-200 bg-amber-50 p-3"
        @submit.prevent="handleClaimSlug"
        aria-label="Claim LinkedIn slug form"
      >
        <div class="text-sm font-semibold text-amber-900">Claim your LinkedIn</div>
        <div class="text-xs text-amber-800">Add your LinkedIn slug so others can connect to you.</div>

        <div>
          <label class="block text-sm font-semibold text-gray-800" for="my_linkedin_slug">LinkedIn link</label>
          <input
            id="my_linkedin_slug"
            class="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100"
            v-model="mySlug"
            placeholder="e.g. linkedin.com/in/janedoe"
            autocomplete="off"
            inputmode="text"
            required
          />
          
        </div>

        <button
          class="inline-flex w-full items-center justify-center rounded-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
          type="submit"
          :disabled="!canClaim"
        >
          <span v-if="claimLoading">Claiming…</span>
          <span v-else>Claim LinkedIn</span>
        </button>

        <p v-if="claimError" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{{ claimError }}</p>
        <p v-else-if="claimSuccess" class="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800" role="status">{{ claimSuccess }}</p>
      </form>

      <form class="mt-4 space-y-3" @submit.prevent="handleAddConnection" aria-label="Add connection form">
        <div>
          <label class="block text-sm font-semibold text-gray-800" for="linkedin_slug">LinkedIn link</label>
          <input
            id="linkedin_slug"
            class="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100"
            v-model="addSlug"
            placeholder="e.g. linkedin.com/in/janedoe"
            autocomplete="off"
            inputmode="text"
            required
          />
        </div>

        <div>
          <label class="block text-sm font-semibold text-gray-800" for="full_name">Full name (optional)</label>
          <input
            id="full_name"
            class="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100"
            v-model="addFullName"
            placeholder="e.g. Jane Doe"
            autocomplete="off"
          />
        </div>

        <button
          class="inline-flex w-full items-center justify-center rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          type="submit"
          :disabled="!canSubmit"
        >
          <span v-if="addLoading">Adding…</span>
          <span v-else>Add connection</span>
        </button>

        <p v-if="addError" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{{ addError }}</p>
        <p v-else-if="addSuccess" class="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800" role="status">{{ addSuccess }}</p>
      </form>

      <div class="my-4 h-px w-full bg-gray-200" role="separator" aria-hidden="true"></div>

      <div class="text-sm font-bold text-gray-800">My connections</div>
      <p v-if="connectionsLoading" class="mt-2 text-sm text-gray-600">Loading connections…</p>
      <p v-else-if="listError" class="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{{ listError }}</p>
      <p v-else-if="connections.length === 0" class="mt-2 text-sm text-gray-600">No connections yet.</p>

      <ul v-else class="mt-2 space-y-2" aria-label="Connections list">
        <li v-for="c in connections" :key="c.id" class="rounded-xl border border-gray-200 bg-white px-3 py-2">
          <div class="text-sm font-semibold text-gray-900">{{ c.full_name }}</div>
          <div class="text-xs text-gray-500">
            <a
              v-if="normalizeLinkedInSlug(c.linkedin_slug)"
              class="text-blue-700 hover:underline"
              :href="linkedinUrl(c.linkedin_slug)"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ c.linkedin_slug }}
            </a>
            <span v-else>—</span>
          </div>
        </li>
      </ul>

      <div class="my-4 h-px w-full bg-gray-200" role="separator" aria-hidden="true"></div>

      <div class="text-sm font-bold text-gray-800">All accounts</div>
      <p v-if="usersLoading" class="mt-2 text-sm text-gray-600">Loading users…</p>
      <p v-else-if="usersError" class="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{{ usersError }}</p>
      <p v-else-if="users.length === 0" class="mt-2 text-sm text-gray-600">No users yet.</p>

      <ul v-else class="mt-2 space-y-2" aria-label="Users list">
        <li v-for="u in users" :key="u.id" class="rounded-xl border border-gray-200 bg-white px-3 py-2">
          <div class="text-sm font-semibold text-gray-900">{{ u.full_name }}</div>
          <div class="text-xs text-gray-500">
            <a
              v-if="normalizeLinkedInSlug(u.linkedin_slug)"
              class="text-blue-700 hover:underline"
              :href="linkedinUrl(u.linkedin_slug)"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ u.linkedin_slug }}
            </a>
            <span v-else>—</span>
          </div>
        </li>
      </ul>
    </section>

    <section class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm" aria-label="Graph visualization section">
      <div class="mb-3 flex items-center justify-between gap-3">
        <h2 class="text-lg font-bold">Network graph</h2>
        <div class="text-sm text-gray-600" v-if="graphLoading">Loading…</div>
      </div>

      <div class="mb-3 rounded-xl border border-gray-200 bg-white p-3" aria-label="Search panel">
        <div class="text-sm font-semibold text-gray-900">Find connection path</div>
        <div class="mt-2 flex gap-2">
          <input
            class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100"
            v-model="searchName"
            placeholder="Search a name…"
            autocomplete="off"
          />
          <button
            class="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-semibold text-gray-900 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
            type="button"
            @click="clearHighlight"
            :disabled="searchLoading"
          >
            Clear
          </button>
        </div>

        <div v-if="searchMatches.length" class="mt-2 rounded-lg border border-gray-200 bg-white">
          <button
            v-for="u in searchMatches"
            :key="u.id"
            type="button"
            class="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-gray-50"
            @click="selectMatch(u)"
          >
            <span class="font-medium text-gray-900">{{ u.full_name }}</span>
            <span class="text-xs text-gray-500">{{ u.linkedin_slug || "(no slug)" }}</span>
          </button>
        </div>

        <p v-if="searchLoading" class="mt-2 text-sm text-gray-600">Searching…</p>
        <p v-else-if="searchError" class="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{{ searchError }}</p>

        <p v-else-if="searchResult && searchResult.degrees === null" class="mt-2 text-sm text-gray-600">No connection path found.</p>
        <p v-else-if="searchResult && typeof searchResult.degrees === 'number'" class="mt-2 text-sm text-gray-700">
          Degrees: <strong>{{ searchResult.degrees }}</strong>
        </p>

        <div v-if="searchResult?.path?.length" class="mt-2 text-xs text-gray-600">
          <span v-for="(p, idx) in searchResult.path" :key="p.id">
            <span class="font-semibold">{{ p.full_name }}</span>
            <span v-if="idx < searchResult.path.length - 1"> → </span>
          </span>
        </div>
      </div>

      <p v-if="status" class="mb-2 text-sm text-gray-600">{{ status }}</p>
      <p v-if="graphError" class="mb-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{{ graphError }}</p>
      <div ref="host" class="min-h-150 w-full overflow-hidden rounded-2xl border border-gray-200 bg-white" aria-label="Graph visualization"></div>
    </section>
  </div>
</template>
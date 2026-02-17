<script setup>
import { computed, onMounted, ref } from "vue";
import * as d3 from "d3";
import { api } from "../api";

const host = ref(null);
const status = ref("Loading your network…");

const me = ref(null);
const connections = ref([]);
const connectionsLoading = ref(false);
const graphLoading = ref(false);

const addSlug = ref("");
const addFullName = ref("");
const addLoading = ref(false);
const addError = ref("");
const addSuccess = ref("");
const listError = ref("");
const graphError = ref("");

const normalizedSlug = computed(() => addSlug.value.trim().toLowerCase());
const canSubmit = computed(() => normalizedSlug.value.length > 0 && !addLoading.value);

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

  node.append("title").text((d) => d.label);

  // Add labels
  const labels = g.append("g")
    .selectAll("text")
    .data(n)
    .join("text")
    .attr("font-size", 13)
    .attr("fill", "#222")
    .attr("text-anchor", "middle")
    .attr("dy", 18)
    .text((d) => d.label);

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

async function loadGraph() {
  graphError.value = "";
  graphLoading.value = true;
  try {
    const data = await api.graph();
    renderGraph(data);
  } catch (e) {
    graphError.value = e?.message || "Failed to load graph";
  } finally {
    graphLoading.value = false;
  }
}

async function loadMe() {
  try {
    me.value = await api.me();
  } catch {
    // non-fatal; UI can work without this.
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
  await Promise.all([loadMe(), loadConnections(), loadGraph()]);
});
</script>

<template>
  <div class="grid gap-4 lg:grid-cols-[380px_1fr]">
    <section class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm lg:sticky lg:top-[76px]" aria-label="Connections panel">
      <h2 class="text-lg font-bold">Connections</h2>
      <p class="mt-1 text-sm text-gray-600" v-if="me?.full_name">Signed in as <strong>{{ me.full_name }}</strong>.</p>

      <form class="mt-4 space-y-3" @submit.prevent="handleAddConnection" aria-label="Add connection form">
        <div>
          <label class="block text-sm font-semibold text-gray-800" for="linkedin_slug">LinkedIn slug</label>
          <input
            id="linkedin_slug"
            class="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100"
            v-model="addSlug"
            placeholder="e.g. janedoe"
            autocomplete="off"
            inputmode="text"
            required
          />
          <div class="mt-1 text-xs text-gray-500">This is the part after linkedin.com/in/</div>
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

      <div class="text-sm font-bold text-gray-800">All connections</div>
      <p v-if="connectionsLoading" class="mt-2 text-sm text-gray-600">Loading connections…</p>
      <p v-else-if="listError" class="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{{ listError }}</p>
      <p v-else-if="connections.length === 0" class="mt-2 text-sm text-gray-600">No connections yet.</p>

      <ul v-else class="mt-2 space-y-2" aria-label="Connections list">
        <li v-for="c in connections" :key="c.id" class="rounded-xl border border-gray-200 bg-white px-3 py-2">
          <div class="text-sm font-semibold text-gray-900">{{ c.full_name }}</div>
          <div class="text-xs text-gray-500">{{ c.linkedin_slug }}</div>
        </li>
      </ul>
    </section>

    <section class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm" aria-label="Graph visualization section">
      <div class="mb-3 flex items-center justify-between gap-3">
        <h2 class="text-lg font-bold">Network graph</h2>
        <div class="text-sm text-gray-600" v-if="graphLoading">Loading…</div>
      </div>
      <p v-if="status" class="mb-2 text-sm text-gray-600">{{ status }}</p>
      <p v-if="graphError" class="mb-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{{ graphError }}</p>
      <div ref="host" class="min-h-[600px] w-full overflow-hidden rounded-2xl border border-gray-200 bg-white" aria-label="Graph visualization"></div>
    </section>
  </div>
</template>
<script setup>
import { onMounted, ref } from "vue";
import * as d3 from "d3";
import { api } from "../api";

const host = ref(null);
const status = ref("Loading graph...");

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
        svg.select("g").attr("transform", event.transform);
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
  g.append("g")
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

    g.selectAll("text")
      .attr("x", (d) => d.x)
      .attr("y", (d) => d.y);
  });
}

onMounted(async () => {
  try {
    const data = await api.graph();
    status.value = "";
    renderGraph(data);
  } catch (e) {
    status.value = e.message || "Failed to load graph";
  }
});
</script>

<template>
  <div>
    <div class="mb-2 text-gray-500 text-base" v-if="status">{{ status }}</div>
    <div ref="host" class="w-full min-h-[600px] border border-gray-200 rounded-xl overflow-hidden bg-white shadow" aria-label="Graph visualization"></div>
  </div>
</template>
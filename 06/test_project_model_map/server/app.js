"use strict";

const path = require("path");
const express = require("express");
const {
  loadDataset,
  findItem,
  filterResources,
  buildSummary,
} = require("./data");

function createApp(options = {}) {
  const rootDir = options.rootDir || path.join(__dirname, "..");
  const dataDir = options.dataDir || path.join(rootDir, "data");
  const dataset = loadDataset(dataDir);

  const app = express();
  app.disable("x-powered-by");

  app.get("/api/health", (req, res) => {
    res.json({
      status: "ok",
      service: "map-api",
      counts: {
        items: dataset.items.length,
        markers: dataset.markers.length,
        populations: dataset.populations.length,
        horses: dataset.horses.length,
        resources: dataset.resources.length,
      },
      ts: new Date().toISOString(),
    });
  });

  app.get("/api/summary", (req, res) => {
    res.json(buildSummary(dataset));
  });

  app.get("/api/items", (req, res) => {
    let items = dataset.items;
    if (req.query.population) {
      const wanted = String(req.query.population);
      items = items.filter((item) => (item.population || []).includes(wanted));
    }
    if (req.query.horse) {
      const wanted = String(req.query.horse);
      items = items.filter((item) => (item.horse || []).includes(wanted));
    }
    if (req.query.craftable === "true" || req.query.craftable === "false") {
      const wanted = req.query.craftable === "true";
      items = items.filter((item) => (item.craftable !== false) === wanted);
    }
    res.json({ items });
  });

  app.get("/api/items/:id", (req, res) => {
    const item = findItem(dataset, req.params.id);
    if (!item) {
      return res.status(404).json({ error: "not_found", message: `找不到兵裝：${req.params.id}` });
    }
    res.json(item);
  });

  app.get("/api/markers", (req, res) => {
    res.json({ markers: dataset.markers });
  });

  app.get("/api/markers/:id", (req, res) => {
    const marker = dataset.markers.find((row) => row.id === req.params.id);
    if (!marker) {
      return res.status(404).json({ error: "not_found", message: `找不到據點：${req.params.id}` });
    }
    res.json(marker);
  });

  app.get("/api/populations", (req, res) => {
    res.json({ populations: dataset.populations });
  });

  app.get("/api/horses", (req, res) => {
    res.json({ horses: dataset.horses });
  });

  app.get("/api/resources", (req, res) => {
    const resources = filterResources(dataset, {
      type: req.query.type,
      level: req.query.level,
    });
    res.json({ resources });
  });

  app.use("/api", (req, res) => {
    res.status(404).json({ error: "not_found", message: `找不到 API：${req.originalUrl}` });
  });

  app.use(express.static(rootDir, { index: "index.html" }));

  app.use((req, res) => {
    res.status(404).type("text/plain").send("404 Not Found");
  });

  app.locals.dataset = dataset;
  return app;
}

module.exports = { createApp };

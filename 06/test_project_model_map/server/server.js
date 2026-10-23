"use strict";

const { createApp } = require("./app");

const port = Number(process.env.PORT || 8000);
const host = process.env.HOST || "0.0.0.0";

const app = createApp();

const server = app.listen(port, host, () => {
  console.log(`三國地圖後端已啟動：http://localhost:${port}`);
  console.log(`API 健康檢查：http://localhost:${port}/api/health`);
});

function shutdown() {
  server.close(() => process.exit(0));
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

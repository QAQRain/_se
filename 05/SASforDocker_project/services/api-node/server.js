const express = require('express');
const { Client } = require('pg');

const app = express();
const PORT = process.env.PORT || 3000;

const dbConfig = {
  host: process.env.DB_HOST || 'postgres',
  port: process.env.DB_PORT || 5432,
  user: process.env.DB_USER || 'sas',
  password: process.env.DB_PASS || 'saspass',
  database: process.env.DB_NAME || 'sasdb',
};

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'api-node', ts: new Date().toISOString() });
});

app.get('/db', async (req, res) => {
  const client = new Client(dbConfig);
  try {
    await client.connect();
    const result = await client.query('SELECT * FROM health_check ORDER BY id');
    res.json({ status: 'ok', rows: result.rows });
  } catch (err) {
    res.status(500).json({ status: 'error', message: err.message });
  } finally {
    try { await client.end(); } catch (e) {}
  }
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`api-node listening on ${PORT}`);
});

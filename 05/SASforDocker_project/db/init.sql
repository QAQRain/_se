CREATE TABLE IF NOT EXISTS health_check (
  id SERIAL PRIMARY KEY,
  note TEXT NOT NULL
);

INSERT INTO health_check (note)
VALUES ('docker microservices ok')
ON CONFLICT DO NOTHING;

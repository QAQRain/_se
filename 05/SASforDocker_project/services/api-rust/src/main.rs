use axum::{extract::State, http::StatusCode, routing::get, Json, Router};
use serde::Serialize;
use std::sync::Arc;
use tokio_postgres::{Config, NoTls};

#[derive(Clone)]
struct AppState {
    db_config: Config,
}

#[derive(Serialize)]
struct Health {
    status: String,
    service: String,
    ts: String,
}

#[derive(Serialize)]
struct DbResponse {
    status: String,
    rows: Option<Vec<serde_json::Value>>,
    message: Option<String>,
}

#[tokio::main]
async fn main() {
    let mut db_config = Config::new();
    db_config
        .host(std::env::var("DB_HOST").unwrap_or_else(|_| "postgres".to_string()))
        .port(std::env::var("DB_PORT").unwrap_or_else(|_| "5432".to_string()).parse().unwrap_or(5432))
        .user(std::env::var("DB_USER").unwrap_or_else(|_| "sas".to_string()))
        .password(std::env::var("DB_PASS").unwrap_or_else(|_| "saspass".to_string()))
        .dbname(std::env::var("DB_NAME").unwrap_or_else(|_| "sasdb".to_string()));

    let state = Arc::new(AppState { db_config });

    let app = Router::new()
        .route("/health", get(health))
        .route("/db", get(db_check))
        .with_state(state);

    let port = std::env::var("PORT").unwrap_or_else(|_| "8080".to_string());
    let addr = format!("0.0.0.0:{port}");
    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    println!("api-rust listening on {port}");
    axum::serve(listener, app).await.unwrap();
}

async fn health() -> Json<Health> {
    Json(Health {
        status: "ok".to_string(),
        service: "api-rust".to_string(),
        ts: chrono_now(),
    })
}

fn chrono_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let t = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default();
    format!("{}", t.as_secs())
}

async fn db_check(State(state): State<Arc<AppState>>) -> Result<Json<DbResponse>, StatusCode> {
    let (client, connection) = state.db_config.connect(NoTls).await.map_err(|e| {
        eprintln!("db connect error: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    tokio::spawn(async move {
        let _ = connection.await;
    });

    let rows = client
        .query("SELECT * FROM health_check ORDER BY id", &[])
        .await
        .map_err(|e| {
            eprintln!("db query error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let mut out: Vec<serde_json::Value> = Vec::new();
    for r in rows {
        let id: i32 = r.get(0);
        let note: Option<String> = r.get(1);
        out.push(serde_json::json!({
            "id": id,
            "note": note,
        }));
    }

    Ok(Json(DbResponse {
        status: "ok".to_string(),
        rows: Some(out),
        message: None,
    }))
}

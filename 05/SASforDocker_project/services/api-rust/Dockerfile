FROM rust:1.88-alpine AS builder

WORKDIR /app

RUN apk add --no-cache musl-dev pkgconfig openssl-dev

COPY Cargo.toml .
COPY src ./src

RUN cargo build --release

FROM alpine:3.20

WORKDIR /app

COPY --from=builder /app/target/release/api-rust /app/api-rust

EXPOSE 8080

CMD ["/app/api-rust"]

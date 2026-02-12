# ---- Build stage ----
FROM golang:1.21-bookworm AS builder

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download

COPY *.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -o /diversiplant-server .

# ---- Runtime stage ----
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /diversiplant-server .
COPY static/ static/

EXPOSE 80 443 8080

CMD ["./diversiplant-server"]

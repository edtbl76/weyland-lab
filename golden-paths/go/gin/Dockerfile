# Golden path Go / gin. Multi-stage: golang build → alpine run. buildkit → registry.weyland.lab/golden-go-gin.
FROM golang:1.23-alpine AS build
WORKDIR /app
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o server .
FROM alpine:3.20
WORKDIR /app
RUN adduser -D -u 10001 appuser && apk add --no-cache curl
COPY --from=build /app/server ./
COPY smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["./server"]

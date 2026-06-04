# Weyland Platform

`mother` is the Weyland platform VM.

## Role

Runs k3s and hosts shared AI platform services.

## Current status

- Ubuntu Server installed
- Static DHCP reservation: 192.168.1.243
- k3s installed
- kubectl configured for non-sudo use
- Helm installed
- Kubernetes namespace created: weyland

## Planned services

- Postgres + pgvector
- Qdrant
- Weyland tool server
- LiteLLM
- n8n
- LangChain / LangGraph / LangSmith learning track
- tracing and eval services

## Boundary

`openclaw` remains the OpenClaw control-plane VM.

`mother` hosts shared AI platform services.

`rogueone` remains the external GPU/dev workstation.

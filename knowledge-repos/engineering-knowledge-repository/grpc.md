---
id: grpc
tags: [protocol, api-design, backend, network, distributed-systems]
surfaces-at: [application-design, nfr-requirements]
related: [rest-constraints, graphql, service-discovery, service-mesh]
complexity: intermediate
---

# gRPC

## What It Is
A high-performance, open-source Remote Procedure Call framework developed by Google. gRPC uses Protocol Buffers (protobuf) for efficient binary serialization and HTTP/2 for transport — enabling bidirectional streaming, multiplexing, and header compression. The service contract is defined in `.proto` files; client and server code is auto-generated for virtually every language. 5-10x more efficient than JSON/HTTP for equivalent payloads.

## When to Apply
- Service-to-service communication in microservices where performance and bandwidth efficiency matter
- Systems requiring bidirectional streaming (real-time data feeds, chat, telemetry)
- Polyglot environments where clients and servers are written in different languages — protobuf generates type-safe code for all
- Internal APIs where strong typing and contract enforcement are priorities

## When Not to Apply
- Public-facing APIs consumed by web browsers — gRPC is not natively supported by browsers without gRPC-Web
- Simple CRUD APIs where JSON readability and REST tooling familiarity matter more than performance
- Teams without protobuf familiarity — learning curve and tooling overhead can outweigh benefits for simple use cases

## Key Concepts
- **Protocol Buffers (protobuf)**: Binary serialization format — smaller and faster than JSON. Schema defined in `.proto` files with version-safe field numbering
- **`.proto` File**: The service contract — defines message types and RPC methods. Used to generate client and server stubs in any supported language
- **HTTP/2**: gRPC's transport — enables multiplexing (multiple streams over one connection), header compression, and flow control
- **Streaming Types**: Unary (request-response), Server Streaming (one request, stream of responses), Client Streaming (stream of requests, one response), Bidirectional Streaming
- **Deadlines/Timeouts**: gRPC clients specify deadlines — servers respect them, canceling work when the deadline passes. More explicit than HTTP timeouts
- **Interceptors**: Middleware for gRPC — authentication, logging, retry logic applied cross-cutting across all RPC calls
- **gRPC-Web**: A proxy layer that translates gRPC to HTTP/1.1-compatible calls for browser clients
- **gRPC-Gateway**: Generates a REST/JSON reverse proxy from protobuf definitions — exposes gRPC services as REST APIs simultaneously
- **Envoy/Istio**: Service mesh sidecars natively support gRPC — load balancing and observability work out of the box

## In Practice
gRPC is used in Method engagements for internal service-to-service APIs in microservices architectures where latency and throughput are NFRs. `.proto` files are stored in a shared repository (proto registry). gRPC-Gateway exposes dual REST/gRPC interfaces where external consumers require REST. Deadlines are set on all client calls. Interceptors handle auth, logging, and retry.

## Engineering Knowledge
💡 **Engineering Knowledge — gRPC**: Use for internal service-to-service calls where performance matters. Protobuf is 5-10x smaller than JSON; HTTP/2 enables multiplexing and streaming. Define contracts in `.proto` files — auto-generate typed clients for every language. Specify deadlines on all calls — gRPC cancellation propagates through the call chain. Use gRPC-Gateway to expose REST alongside gRPC for external consumers. Native streaming support makes gRPC the right choice for telemetry pipelines and real-time feeds. Not for browser-facing APIs without gRPC-Web. → `engineering-knowledge-repository/api-design/grpc.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — REST is the alternative for resource-oriented, human-readable APIs
- [GraphQL](graphql.md) — GraphQL is the alternative for flexible client-driven data queries
- [Service Discovery](../cloud-patterns/service-discovery.md) — gRPC services need service discovery like any microservice
- [Service Mesh](../architectural-styles/service-mesh.md) — service mesh handles gRPC load balancing and observability

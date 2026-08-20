---
id: consistent-hashing
tags: [pattern, distributed-systems, backend]
surfaces-at: [application-design, infrastructure-design]
related: [database-sharding, load-balancing, caching-strategies, distributed-locks]
complexity: advanced
---

# Consistent Hashing

## What It Is
A distributed hashing scheme that minimizes data movement when nodes are added to or removed from a cluster. In standard modular hashing (`hash(key) % N`), changing N (the number of nodes) remaps almost all keys — requiring massive data redistribution. Consistent hashing arranges nodes on a virtual ring; adding or removing a node affects only the keys that were mapped to that node's neighbors. This makes consistent hashing essential for distributed caches, databases, and load balancers that need to scale without full reshuffling.

## When to Apply
- Distributing data across a variable number of nodes (distributed caches, sharded databases)
- Load balancing where session affinity or data locality matters
- Any distributed system where nodes join and leave and remapping cost must be minimized

## Key Concepts
- **Hash Ring**: A conceptual circle (0 to 2^32) where both nodes and keys are mapped via a hash function. Each key is owned by the first node clockwise from its position on the ring
- **Node Addition**: Adding a node inserts it at a position on the ring. Only the keys between the new node and its predecessor are remapped — typically 1/N of all keys where N is the total node count
- **Node Removal**: Removing a node remaps only that node's keys to the next node clockwise — again approximately 1/N of keys
- **Virtual Nodes (Vnodes)**: Each physical node is represented by multiple points on the ring. Improves load distribution when node capacities are unequal or when the number of physical nodes is small. Cassandra and DynamoDB use virtual nodes extensively
- **Replication**: Keys can be replicated to the next K nodes clockwise for fault tolerance. Cassandra's replication factor determines how many virtual node positions each key is written to
- **Hot Spots**: Without virtual nodes, uneven hash distribution creates hot spots — some nodes receive more traffic than others. Vnodes mitigate this by spreading each physical node's responsibility across multiple ring positions
- **Implementations**: Memcached client libraries implement consistent hashing for cache cluster scaling. Cassandra and DynamoDB use consistent hashing for data distribution. Nginx and HAProxy support consistent hashing for upstream load balancing with session affinity
- **Rendezvous Hashing**: An alternative to ring-based consistent hashing — for each key, score all nodes by `hash(key, node)` and pick the highest. Simpler; equivalent minimal disruption on node changes. Used in some CDN and load balancer implementations

## In Practice
Method uses consistent hashing in distributed cache configurations (Redis Cluster, client-side Memcached sharding) to minimize cache invalidation on cluster topology changes. Database sharding with Citus uses hash-based distribution; manual resharding is performed with minimal disruption during scaling events.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Consistent Hashing**: Standard modular hashing (`% N`) is catastrophic when N changes — use consistent hashing whenever nodes are added or removed dynamically. Virtual nodes are essential for even load distribution when physical node count is small. When a node is added or removed, only its neighbors' data moves — approximately 1/N of all keys. If you're using a distributed cache (Redis Cluster, Memcached) or a distributed database (Cassandra, DynamoDB), consistent hashing is already happening under the hood — understanding it helps you reason about rebalancing behavior during scaling events. → `engineering-knowledge-repository/consistent-hashing.md`

## Related Entries
- [Database Sharding](database-sharding.md) — consistent hashing minimizes rebalancing cost when the shard count changes
- [Load Balancing](load-balancing.md) — consistent hashing in load balancers provides session affinity with minimal disruption on server changes
- [Caching Strategies](caching-strategies.md) — distributed caches use consistent hashing to distribute keys across cache nodes
- [Distributed Locks](distributed-locks.md) — distributed lock implementations on Redis Cluster use consistent hashing for key routing

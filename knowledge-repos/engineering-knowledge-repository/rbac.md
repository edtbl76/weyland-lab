---
id: rbac
tags: [pattern, security, backend]
surfaces-at: [nfr-requirements, functional-design, application-design]
related: [principle-of-least-privilege, oauth2-oidc, zero-trust-security, api-security]
complexity: intermediate
---

# Role-Based Access Control (RBAC)

## What It Is
An access control model where permissions are assigned to roles, and roles are assigned to users (or services). Instead of granting permissions directly to individuals — which creates management complexity at scale — permissions are grouped into roles (Admin, Editor, Viewer, Manager) and users are assigned roles. Changing a user's permissions means changing their role, not updating dozens of individual permission grants.

## When to Apply
- Any multi-user system with different access levels
- Systems where user permissions are based on their job function or organizational role
- When auditors require clear documentation of who has access to what and why
- Microservices where services have different levels of access to shared resources

## When Not to Apply
- Single-user or internal tools where the overhead of role management isn't warranted
- Very fine-grained access requirements (e.g., user can only access their own records) — RBAC may need to be supplemented with attribute-based access control (ABAC) or resource-level authorization
- When roles would proliferate to the point where each user effectively has a unique role (then you're back to user-based permissions)

## Key Concepts
- **Role**: A named collection of permissions — Admin, Editor, ReadOnly, BillingManager
- **Permission**: A specific action on a resource — `orders:read`, `users:write`, `reports:delete`
- **Role Assignment**: A user is assigned one or more roles — roles can be additive
- **Role Hierarchy**: Roles can inherit from parent roles — Admin inherits all Editor permissions, Editor inherits all Viewer permissions
- **Separation of Duties**: RBAC enables enforcement — a user who approves purchases cannot also be the one who makes them
- **Kubernetes RBAC**: The native authorization mechanism in Kubernetes — ClusterRoles and Roles grant access to Kubernetes resources; ClusterRoleBindings and RoleBindings assign them to service accounts
- **ABAC (Attribute-Based Access Control)**: The more flexible alternative — permissions based on attributes of the user, resource, and environment. More powerful than RBAC, more complex to manage.

## In Practice
RBAC is the standard authorization model in Method application engagements. Implement at the API gateway or application layer; use JWT claims to carry role information. Define roles from user needs, not technical capabilities — start with the minimum viable role set and add roles as distinct permission groups emerge. Kubernetes RBAC governs service account access to cluster resources.

## Engineering Knowledge
💡 **Engineering Knowledge — RBAC**: Assign permissions to roles, assign roles to users — not permissions directly to users. When a user's job changes, change their role; don't audit 50 individual permission grants. Define roles from actual job functions. In JWT-based systems, roles are claims in the access token. Kubernetes RBAC governs what service accounts can do in the cluster — every microservice should have its own service account with minimal cluster permissions. → `engineering-knowledge-repository/security/rbac.md`

## Related Entries
- [Principle of Least Privilege](principle-of-least-privilege.md) — RBAC implements least privilege at the user/service authorization level
- [OAuth2/OIDC](oauth2-oidc.md) — roles are typically encoded as JWT claims in OIDC-based systems
- [API Security](api-security.md) — RBAC authorization is enforced at the API layer

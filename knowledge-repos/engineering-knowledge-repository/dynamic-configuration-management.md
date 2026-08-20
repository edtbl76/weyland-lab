---
id: dynamic-configuration-management
tags: [pattern, infrastructure, backend]
surfaces-at: [application-design, functional-design]
related: [feature-flags, secrets-management, twelve-factor-app, environment-management, kubernetes]
complexity: intermediate
---

# Dynamic Configuration Management

## What It Is
The practice of managing application configuration values that can change at runtime — without requiring a redeployment or restart. While static configuration (environment variables baked in at deploy time) is sufficient for infrastructure-level settings, dynamic configuration allows operators and product teams to change application behavior in production instantly: adjust rate limits, enable/disable features, tune algorithm parameters, or change connection pool sizes. Dynamic configuration is a prerequisite for feature flags and real-time operational control.

## When to Apply
- Settings that operations teams need to adjust without a deploy cycle (rate limits, thresholds, timeouts)
- Feature toggles that product teams need to control independently of deployments
- Algorithm or model parameters that data teams need to tune in production
- Multi-environment configuration where values differ by tenant, region, or traffic segment
- When you need to change behavior mid-incident without triggering a new deployment

## Key Concepts
- **Static vs. Dynamic Configuration**: Static config is set at deploy time (environment variables, config maps). Dynamic config is stored externally and read at request time or on a polling interval. The distinction determines who can change it (SRE/dev for static; ops/product/data for dynamic) and how fast it takes effect (minutes for static; seconds for dynamic)
- **Configuration Stores**: Common dynamic configuration backends:
  - *AWS AppConfig*: Managed configuration store with deployment strategies (gradual rollout of config changes), validation, and CloudWatch integration
  - *HashiCorp Consul*: Key-value store with watch notifications; common in Kubernetes environments
  - *Redis*: Simple, fast key-value store usable for runtime config; lacks change history and deployment controls
  - *LaunchDarkly / Unleash*: Feature flag platforms that also serve as dynamic configuration stores
  - *Kubernetes ConfigMaps*: Can be mounted as volumes and reloaded without restart in some frameworks
- **Configuration Refresh**:
  - *Poll*: Application polls the config store on an interval (e.g., every 30 seconds). Simple; slight lag between config change and effect
  - *Push / Watch*: Config store notifies the application of changes (Consul watches, AWS AppConfig callbacks). Faster propagation; more complex
  - *Per-Request*: Configuration is fetched on every request. Zero lag; higher latency and cost. Use for configuration that changes frequently and affects individual requests
- **Schema and Validation**: Dynamic configuration should be validated before it takes effect. Type errors or invalid values in a config change can be as impactful as a bad deployment. AppConfig supports JSON schema validation; feature flag platforms validate flag types
- **Audit and History**: Every configuration change should be logged with who made the change, what changed, and when. This is critical for post-incident analysis: "was the rate limit change before or after the latency spike?"
- **Separation of Concerns**: Configuration values (operational parameters) should be separated from feature flags (release toggles) and secrets (credentials). Each category has different security, lifecycle, and access control requirements
- **Testing Dynamic Configuration**: Configurations must be testable before they reach production. AppConfig deployment strategies (canary rollout to 10% of instances) and flag evaluation in staging prevent bad config from affecting all users simultaneously

## In Practice
Method services use AWS AppConfig for operational parameters (rate limits, connection pool sizes, timeout values) and LaunchDarkly for feature flags. Config changes go through AppConfig's deployment pipeline with JSON schema validation. All config changes are logged in CloudTrail. Application services poll AppConfig on a 30-second interval for non-latency-sensitive config; per-request evaluation is used only for feature flags affecting individual users.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Dynamic Configuration Management**: Dynamic configuration is how you retain operational control after deployment — the ability to change rate limits, toggle features, or adjust algorithm parameters without a redeploy. The trap is treating config changes as lower-risk than code changes; a bad config value can take down a service just as effectively as a bad deployment. Apply the same controls: validation, staged rollout, audit log, and rollback capability. Keep feature flags separate from operational config — they have different owners, different lifecycles, and different risk profiles. → `engineering-knowledge-repository/dynamic-configuration-management.md`

## Related Entries
- [Feature Flags](feature-flags.md) — feature flags are a specialized form of dynamic configuration for controlling feature exposure
- [Secrets Management](secrets-management.md) — secrets are distinct from configuration and require different security controls
- [Twelve-Factor App](twelve-factor-app.md) — Factor III (config) advocates separating config from code; dynamic config extends this to runtime-changeable values
- [Environment Management](environment-management.md) — dynamic configuration enables consistent application code with environment-specific behavior
- [Kubernetes](kubernetes.md) — ConfigMaps and environment variables in Kubernetes provide the static config layer that dynamic config extends

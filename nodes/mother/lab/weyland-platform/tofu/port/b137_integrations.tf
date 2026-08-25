# B137 — the four Port integrations, codified from the LIVE api.port.io definition (2026-08-24).
#
# Until now these existed ONLY inside Port's UI: no source of truth, no review trail, and nothing that
# would notice their loss. `docs/runbooks/port.md` claimed the B60 split kept schema in OpenTofu; the
# integrations were the largest hole in that claim.
#
# HOW THESE WERE PRODUCED — read before editing. Every block below was generated from the live API and
# then proved with `tofu import` + a NO-OP `tofu plan`. Do NOT use `tofu plan -generate-config-out`:
# the port-labs provider's SOURCE name differs from its `port_` resource prefix, so generated config
# carries `provider = port-labs` and poisons `init` (docs/runbooks/opentofu.md).
#
# WHAT IS DELIBERATELY NOT MANAGED HERE
#   * `version` — optional+COMPUTED in the provider, and left unset ON PURPOSE. Port upgrades its
#     hosted integrations on its own schedule (github-ocean moved 6.8.1 -> 6.9.4 in two days;
#     sonarqube 0.1.439 -> 0.1.442). Pinning it would make `tofu plan` permanently dirty, which is the
#     exact failure this backlog item exists to cure.
#   * `spec.appSpec.*` — the provider has no attribute for it, AND it is not durable anyway: the three
#     Port-hosted integrations re-register and push their own appSpec, silently overwriting
#     server-side edits (that is how `incrementalSyncEnabled` reverted on 2026-08-23). It is recorded
#     in the runbook instead, because a tofu attribute that cannot hold its value is worse than none.
#   * The GitHub App private key, Linear API token and Sonar token. Port stores those as
#     `__<INTEGRATION>_..._KEY` references; they never appear in `config` and never belong in git.
#
# WHY `config` IS SAFE TO MANAGE WHILE appSpec IS NOT: `config` is the RESOURCE MAPPING (which kinds,
# which selectors, which blueprint each record lands in). Nothing but a human writes it. `appSpec` is
# runtime state the hosted integration owns.
#
# THE RISK THAT WAS ACTUALLY TAKEN: importing `github-weyland` touches a live OAuth-connected
# integration feeding six repositories, which is why B137 refused to bundle it into B131. The
# mitigation is that import + a no-op plan proves an apply is a no-op. If you edit a mapping here,
# re-verify against the live system afterwards — a clean plan only proves the code matches the code,
# and every one of these mappings is a jq expression Port evaluates, not a value tofu can check.

resource "port_integration" "github_weyland" {
  installation_id       = "github-weyland"
  installation_app_type = "github-ocean"
  title                 = null
  config = jsonencode({
    "resources" = [
      {
        "kind" = "repository"
        "selector" = {
          "query" = ".name | IN(\"midi_real_book\", \"stud.io\", \"weyland-lab\", \"Algopedia\", \"emangini-tailwind-nextjs-contentlayer\", \"ServiceTransformation\")"
          "include" = [
            "teams",
          ]
          "includedFiles" = [
            "README.md",
            "CODEOWNERS",
            ".gitignore",
            ".github/pull_request_template.md",
          ]
        }
        "port" = {
          "entity" = {
            "mappings" = {
              "identifier" = ".name"
              "blueprint"  = "\"githubRepository\""
              "title"      = ".name"
              "properties" = {
                "codeowners"    = ".__includedFiles[\"CODEOWNERS\"]"
                "defaultBranch" = ".default_branch"
                "description"   = "if .description then .description else \"\" end"
                "gitignore"     = ".__includedFiles[\".gitignore\"]"
                "language"      = "if .language then .language else \"\" end"
                "last_push"     = ".pushed_at"
                "pr_template"   = ".__includedFiles[\".github/pull_request_template.md\"]"
                "readme"        = ".__includedFiles[\"README.md\"]"
                "url"           = ".html_url"
                "visibility"    = "if .private then \"private\" else \"public\" end"
              }
              "relations" = {
                "githubTeams" = "[.__teams[].id | tostring]"
              }
            }
          }
        }
      },
      {
        "kind" = "pull-request"
        "selector" = {
          "query" = ".base.repo.name | IN(\"weyland-lab\", \"stud.io\", \"midi_real_book\", \"Algopedia\", \"emangini-tailwind-nextjs-contentlayer\", \"ServiceTransformation\")"
        }
        "port" = {
          "entity" = {
            "mappings" = {
              "identifier" = ".id | tostring"
              "blueprint"  = "\"githubPullRequest\""
              "title"      = ".title"
              "properties" = {
                "prNumber"      = ".number"
                "status"        = ".state"
                "link"          = ".html_url"
                "branch"        = ".head.ref"
                "createdAt"     = ".created_at"
                "closedAt"      = ".closed_at"
                "mergedAt"      = ".merged_at"
                "has_assignees" = "(.assignees | length) > 0"
                "has_reviewers" = "(.requested_reviewers | length) > 0"
              }
              "relations" = {
                "repository" = ".base.repo.name"
              }
            }
          }
        }
      },
    ]
  })
}

resource "port_integration" "weyland_cluster" {
  installation_id       = "weyland-cluster"
  installation_app_type = "K8S EXPORTER"
  title                 = "weyland-cluster"
  config = jsonencode({
    "resources" = [
      {
        "kind" = "v1/namespaces"
        "selector" = {
          "query" = ".metadata.name | contains(\"kube-system\")"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = "env.CLUSTER_NAME"
                "blueprint"  = "\"k8s_cluster\""
                "title"      = "env.CLUSTER_NAME"
              },
            ]
          }
        }
      },
      {
        "kind" = "v1/namespaces"
        "selector" = {
          "query" = ".metadata.name | startswith(\"kube\") | not"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = ".metadata.name + \"-\" + env.CLUSTER_NAME"
                "blueprint"  = "\"k8s_namespace\""
                "title"      = ".metadata.name"
                "properties" = {
                  "creationTimestamp" = ".metadata.creationTimestamp"
                  "labels"            = ".metadata.labels"
                }
                "relations" = {
                  "Cluster" = "env.CLUSTER_NAME"
                }
              },
            ]
          }
        }
      },
      {
        "kind" = "v1/nodes"
        "selector" = {
          "query" = "true"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = "(.metadata.name) | (split(\".\")|join(\"_\")) + \"-\" + env.CLUSTER_NAME"
                "blueprint"  = "\"k8s_node\""
                "title"      = ".metadata.name + \"-\" + env.CLUSTER_NAME"
                "properties" = {
                  "creationTimestamp" = ".metadata.creationTimestamp"
                  "totalCPU"          = ".status.allocatable.cpu"
                  "totalMemory"       = ".status.allocatable.memory"
                  "labels"            = ".metadata.labels"
                  "kubeletVersion"    = ".status.nodeInfo.kubeletVersion | split(\"-\") | .[0]"
                  "ready"             = ".status.conditions[] | select(.type == \"Ready\") | .status"
                }
                "relations" = {
                  "Cluster" = "env.CLUSTER_NAME"
                }
              },
            ]
          }
        }
      },
      {
        "kind" = "apps/v1/deployments"
        "selector" = {
          "query" = ".metadata.namespace | startswith(\"kube\") | not"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = ".metadata.name + \"-Deployment-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME"
                "blueprint"  = "\"k8s_workload\""
                "title"      = ".metadata.name"
                "properties" = {
                  "kind"              = "\"Deployment\""
                  "creationTimestamp" = ".metadata.creationTimestamp"
                  "replicas"          = ".spec.replicas"
                  "hasPrivileged"     = ".spec.template.spec.containers | [.[].securityContext.privileged] | any"
                  "hasLatest"         = ".spec.template.spec.containers[].image | contains(\":latest\")"
                  "hasLimits"         = ".spec.template.spec.containers | all(has(\"resources\") and (.resources.limits.memory and .resources.limits.cpu))"
                  "strategyConfig"    = ".spec.strategy // {}"
                  "strategy"          = ".spec.strategy.type"
                  "availableReplicas" = ".status.availableReplicas"
                  "labels"            = ".metadata.labels"
                  "containers"        = "(.spec.template.spec.containers | map({name, image, resources}))"
                  "isHealthy"         = "if .spec.replicas == .status.availableReplicas then \"Healthy\" else \"Unhealthy\" end"
                }
                "relations" = {
                  "Namespace" = ".metadata.namespace + \"-\" + env.CLUSTER_NAME"
                }
              },
            ]
          }
        }
      },
      {
        "kind" = "apps/v1/statefulsets"
        "selector" = {
          "query" = ".metadata.namespace | startswith(\"kube\") | not"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = ".metadata.name + \"-StatefulSet-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME"
                "blueprint"  = "\"k8s_workload\""
                "title"      = ".metadata.name"
                "properties" = {
                  "kind"              = "\"StatefulSet\""
                  "labels"            = ".metadata.labels"
                  "creationTimestamp" = ".metadata.creationTimestamp"
                  "strategyConfig"    = ".spec.strategy // {}"
                  "replicas"          = ".spec.replicas"
                  "availableReplicas" = ".status.availableReplicas"
                  "hasLatest"         = ".spec.template.spec.containers[].image | contains(\":latest\")"
                  "hasPrivileged"     = ".spec.template.spec.containers | [.[].securityContext.privileged] | any"
                  "hasLimits"         = ".spec.template.spec.containers | all(has(\"resources\") and (.resources.limits.memory and .resources.limits.cpu))"
                  "containers"        = "(.spec.template.spec.containers | map({name, image, resources}))"
                  "isHealthy"         = "if .spec.replicas == .status.availableReplicas then \"Healthy\" else \"Unhealthy\" end"
                }
                "relations" = {
                  "Namespace" = ".metadata.namespace + \"-\" + env.CLUSTER_NAME"
                }
              },
            ]
          }
        }
      },
      {
        "kind" = "apps/v1/daemonsets"
        "selector" = {
          "query" = ".metadata.namespace | startswith(\"kube\") | not"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = ".metadata.name + \"-DaemonSet-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME"
                "blueprint"  = "\"k8s_workload\""
                "title"      = ".metadata.name"
                "properties" = {
                  "kind"              = "\"DaemonSet\""
                  "creationTimestamp" = ".metadata.creationTimestamp"
                  "replicas"          = ".spec.replicas"
                  "strategyConfig"    = ".spec.strategy // {}"
                  "availableReplicas" = ".status.availableReplicas"
                  "hasPrivileged"     = ".spec.template.spec.containers | [.[].securityContext.privileged] | any"
                  "labels"            = ".metadata.labels"
                  "hasLatest"         = ".spec.template.spec.containers[].image | contains(\":latest\")"
                  "hasLimits"         = ".spec.template.spec.containers | all(has(\"resources\") and (.resources.limits.memory and .resources.limits.cpu))"
                  "containers"        = "(.spec.template.spec.containers | map({name, image, resources}))"
                  "isHealthy"         = "if .spec.replicas == .status.availableReplicas then \"Healthy\" else \"Unhealthy\" end"
                }
                "relations" = {
                  "Namespace" = ".metadata.namespace + \"-\" + env.CLUSTER_NAME"
                }
              },
            ]
          }
        }
      },
      {
        "kind" = "apps/v1/replicasets"
        "selector" = {
          "query" = ".metadata.namespace | startswith(\"kube\") | not"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = ".metadata.name + \"-ReplicaSet-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME"
                "blueprint"  = "\"k8s_replicaSet\""
                "title"      = ".metadata.name"
                "properties" = {
                  "creationTimestamp" = ".metadata.creationTimestamp"
                  "replicas"          = ".spec.replicas"
                  "hasPrivileged"     = ".spec.template.spec.containers | [.[].securityContext.privileged] | any"
                  "hasLatest"         = ".spec.template.spec.containers[].image | contains(\":latest\")"
                  "hasLimits"         = ".spec.template.spec.containers | all(has(\"resources\") and (.resources.limits.memory and .resources.limits.cpu))"
                  "strategy"          = ".spec.strategy.type // \"\""
                  "availableReplicas" = ".status.availableReplicas"
                  "labels"            = ".metadata.labels"
                  "containers"        = "(.spec.template.spec.containers | map({name, image, resources}))"
                  "isHealthy"         = "if .spec.replicas == .status.availableReplicas then \"Healthy\" else \"Unhealthy\" end"
                }
                "relations" = {
                  "replicaSetManager" = ".metadata.ownerReferences[0].name + \"-\" + .metadata.ownerReferences[0].kind + \"-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME // []"
                  "workload" = {
                    "combinator" = "\"and\""
                    "rules" = [
                      {
                        "operator" = "\"=\""
                        "property" = "\"workload_identifier\""
                        "value"    = ".metadata.ownerReferences[0].name + \"-\" + .metadata.ownerReferences[0].kind + \"-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME // []"
                      },
                    ]
                  }
                }
              },
            ]
          }
        }
      },
      {
        "kind" = "v1/pods"
        "selector" = {
          "query" = "(.metadata.ownerReferences[0].kind == \"ReplicaSet\") and (.metadata.namespace | startswith(\"kube\") | not)"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = ".metadata.name + \"-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME"
                "blueprint"  = "\"k8s_pod\""
                "title"      = ".metadata.name"
                "properties" = {
                  "startTime" = ".status.startTime"
                  "phase"     = ".status.phase"
                  "labels"    = ".metadata.labels"
                }
                "relations" = {
                  "replicaSet" = ".metadata.ownerReferences[0].name + \"-\" + \"ReplicaSet\" + \"-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME"
                  "Node"       = "if .spec.nodeName != null then (.spec.nodeName | split(\".\")|join(\"_\")) + \"-\" + env.CLUSTER_NAME else null end"
                }
              },
            ]
          }
        }
      },
      {
        "kind" = "v1/pods"
        "selector" = {
          "query" = "(.metadata.ownerReferences[0].kind != \"ReplicaSet\") and (.metadata.namespace | startswith(\"kube\") | not)"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = ".metadata.name + \"-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME"
                "blueprint"  = "\"k8s_pod\""
                "title"      = ".metadata.name"
                "properties" = {
                  "startTime" = ".status.startTime"
                  "phase"     = ".status.phase"
                  "labels"    = ".metadata.labels"
                }
                # B137, 2026-08-24 — BOTH workload relations are now GUARDED on ownerReferences existing.
                #
                # This selector is `ownerReferences[0].kind != "ReplicaSet"`, and in jq `null != "ReplicaSet"`
                # is TRUE — so a pod with NO ownerReferences at all lands here, and the relation below then
                # string-concatenated nulls into an identifier that matches nothing. Woodpecker's kubernetes
                # backend creates every pipeline step pod as a BARE pod with no owner, so enabling the
                # nightly-images cron produced 176 audit-log FAILUREs in a single 05:01 run, all for one
                # identifier, recurring every night and on every manual pipeline.
                #
                # Guarding the relation rather than the selector on purpose: the pod entity is still worth
                # having, it just has no workload to point at. Excluding the woodpecker namespace instead
                # would have hidden the symptom while leaving every other owner-less pod broken.
                "relations" = {
                  "k8s_workload" = "if ((.metadata.ownerReferences // []) | length) > 0 then .metadata.ownerReferences[0].name + \"-\" + .metadata.ownerReferences[0].kind + \"-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME else null end"
                  "Node"         = "if .spec.nodeName != null then (.spec.nodeName | split(\".\")|join(\"_\")) + \"-\" + env.CLUSTER_NAME else null end"
                  "workload" = {
                    "combinator" = "\"and\""
                    "rules" = [
                      {
                        "operator" = "\"=\""
                        "property" = "\"workload_identifier\""
                        "value"    = "if ((.metadata.ownerReferences // []) | length) > 0 then .metadata.ownerReferences[0].name + \"-\" + .metadata.ownerReferences[0].kind + \"-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME else null end"
                      },
                    ]
                  }
                }
              },
            ]
          }
        }
      },
      {
        "kind" = "networking.istio.io/v1beta1/gateways"
        "selector" = {
          "query" = "true"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = ".metadata.name + \"-\" + .metadata.namespace"
                "blueprint"  = "\"istio_gateway\""
                "title"      = ".metadata.name"
                "properties" = {
                  "ports"    = "[.spec.servers[].port.number]"
                  "name"     = ".metadata.name"
                  "labels"   = ".metadata.labels"
                  "selector" = ".spec.selector"
                }
                "relations" = {
                  "namespace" = ".metadata.namespace + \"-\" + env.CLUSTER_NAME"
                }
              },
            ]
          }
        }
      },
      {
        "kind" = "networking.istio.io/v1beta1/virtualservices"
        "selector" = {
          "query" = "true"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = ".metadata.name + \"-\" + .metadata.namespace"
                "blueprint"  = "\"istio_virtual_service\""
                "title"      = ".metadata.name"
                "properties" = {
                  "hosts"  = ".spec.hosts"
                  "labels" = ".metadata.labels"
                }
                "relations" = {
                  "gateway"   = "if .spec.gateways then .spec.gateways[0] + \"-\" + .metadata.namespace else null end"
                  "namespace" = ".metadata.namespace + \"-\" + env.CLUSTER_NAME"
                }
              },
            ]
          }
        }
      },
      {
        "kind" = "batch/v1/jobs"
        "selector" = {
          "query" = ".metadata.namespace | startswith(\"kube\") | not"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = ".metadata.name + \"-Job-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME"
                "blueprint"  = "\"k8s_workload\""
                "title"      = ".metadata.name"
                # B137, 2026-08-24 — these two batch mappings were added on 2026-08-22 by copy-pasting the
                # DEPLOYMENTS mapping, and three of the copied lines were wrong for a Job. Found by reading
                # the live entities rather than the config, which is the only way any of it shows:
                #
                #   * `kind` was hardcoded `"Deployment"`, so all 27 Job entities reported themselves as
                #     Deployments. It is NOT set to "Job" here because `k8s_workload.kind` is an enum of
                #     StatefulSet/DaemonSet/Deployment/Rollout and Port drops an out-of-enum value SILENTLY
                #     (the same trap that made `ci_pipeline` ingest return ok:true and write nothing). The
                #     enum lives on an integration-owned blueprint, so extending it is its own decision —
                #     filed, not smuggled in here. Until then the property is simply not asserted: a null is
                #     honest, "Deployment" was false data feeding a scorecard.
                #   * `isHealthy` compared `.spec.replicas` to `.status.availableReplicas`. A Job has
                #     NEITHER field, so it evaluated `null == null` and every Job — including a failed one —
                #     reported **Healthy**. Same class as the five silent-failure defects: an absent result
                #     standing in for a successful one, in the field whose entire job is to say otherwise.
                #   * `replicas` / `strategy` / `strategyConfig` do not exist on a Job at all.
                #
                # A Job is healthy if it succeeded or is still running; anything else (failed, or never
                # started) is not. Deliberately not `.status.failed == 0`, which is true before it starts.
                "properties" = {
                  # B145, 2026-08-25 — now a real value. It was `null` because `k8s_workload.kind` was an
                  # enum of StatefulSet/DaemonSet/Deployment/Rollout and Port drops an out-of-enum value
                  # SILENTLY, so writing "Job" would have looked like it worked and written nothing.
                  # The enum was extended with Job + CronJob, and the concern that the integration would
                  # revert it was TESTED rather than assumed: extended, restarted the exporter (which runs
                  # CREATE_DEFAULT_RESOURCES=true), re-read — the change SURVIVED. Consistent with the
                  # blueprint's updatedAt having sat unchanged for 66 days across 3 pod restarts.
                  "kind"              = "\"Job\""
                  "creationTimestamp" = ".metadata.creationTimestamp"
                  "replicas"          = ".spec.parallelism"
                  "hasPrivileged"     = ".spec.template.spec.containers | [.[].securityContext.privileged] | any"
                  "hasLatest"         = ".spec.template.spec.containers[].image | contains(\":latest\")"
                  "hasLimits"         = ".spec.template.spec.containers | all(has(\"resources\") and (.resources.limits.memory and .resources.limits.cpu))"
                  "availableReplicas" = ".status.active"
                  "labels"            = ".metadata.labels"
                  "containers"        = "(.spec.template.spec.containers | map({name, image, resources}))"
                  "isHealthy"         = "if ((.status.succeeded // 0) > 0 or (.status.active // 0) > 0) then \"Healthy\" else \"Unhealthy\" end"
                }
                "relations" = {
                  "Namespace" = ".metadata.namespace + \"-\" + env.CLUSTER_NAME"
                }
              },
            ]
          }
        }
      },
      {
        "kind" = "batch/v1/cronjobs"
        "selector" = {
          "query" = ".metadata.namespace | startswith(\"kube\") | not"
        }
        "port" = {
          "entity" = {
            "mappings" = [
              {
                "identifier" = ".metadata.name + \"-CronJob-\" + .metadata.namespace + \"-\" + env.CLUSTER_NAME"
                "blueprint"  = "\"k8s_workload\""
                "title"      = ".metadata.name"
                # B137, 2026-08-24 — this mapping produced **ZERO entities**, and the row in B137's own
                # validation table ("k8s_workload contains Job entities") passed anyway because it only ever
                # looked at Jobs. A CronJob's pod template is at `.spec.jobTemplate.spec.template.spec`,
                # NOT `.spec.template.spec`; four properties dereferenced a path that does not exist, so
                # nothing was ever written. Nothing reported this: an entity that is never created leaves no
                # trace at all — not even an audit FAILURE, which is what the pod-relation bug at least had.
                #
                # `kind` is now "CronJob" — see the Jobs mapping above for the enum test. A CronJob has no
                # replicas and no health of its own; the meaningful state is whether it is SUSPENDED, which
                # is the one way a scheduled job silently stops — the exact failure that cost four days on
                # `nightly-images`.
                "properties" = {
                  "kind"              = "\"CronJob\""
                  "creationTimestamp" = ".metadata.creationTimestamp"
                  "hasPrivileged"     = ".spec.jobTemplate.spec.template.spec.containers | [.[].securityContext.privileged] | any"
                  "hasLatest"         = ".spec.jobTemplate.spec.template.spec.containers[].image | contains(\":latest\")"
                  "hasLimits"         = ".spec.jobTemplate.spec.template.spec.containers | all(has(\"resources\") and (.resources.limits.memory and .resources.limits.cpu))"
                  "availableReplicas" = "((.status.active // []) | length)"
                  "labels"            = ".metadata.labels"
                  "containers"        = "(.spec.jobTemplate.spec.template.spec.containers | map({name, image, resources}))"
                  "isHealthy"         = "if (.spec.suspend // false) then \"Unhealthy\" else \"Healthy\" end"
                }
                "relations" = {
                  "Namespace" = ".metadata.namespace + \"-\" + env.CLUSTER_NAME"
                }
              },
            ]
          }
        }
      },
    ]
  })
}

resource "port_integration" "linear" {
  installation_id       = "linear"
  installation_app_type = "linear"
  title                 = null
  config = jsonencode({
    "deleteDependentEntities"      = true
    "createMissingRelatedEntities" = true
    "enableMergeEntity"            = true
    "entityDeletionThreshold"      = 0.9
    "resources" = [
      {
        "kind" = "team"
        "selector" = {
          "query" = "true"
        }
        "port" = {
          "entity" = {
            "mappings" = {
              "identifier" = ".key"
              "title"      = ".name"
              "blueprint"  = "\"linearTeam\""
              "properties" = {
                "description"   = ".description"
                "workspaceName" = ".organization.name"
                "url"           = "\"https://linear.app/\" + .organization.urlKey + \"/team/\" + .key"
              }
            }
          }
        }
      },
      {
        "kind" = "label"
        "selector" = {
          "query" = "true"
        }
        "port" = {
          "entity" = {
            "mappings" = {
              "identifier" = ".id"
              "title"      = ".name"
              "blueprint"  = "\"linearLabel\""
              "properties" = {
                "isGroup" = ".isGroup"
              }
              "relations" = {
                "parentLabel" = ".parent.id"
                "childLabels" = "[.children.edges[].node.id]"
              }
            }
          }
        }
      },
      {
        "kind" = "issue"
        "selector" = {
          "query" = "true"
        }
        "port" = {
          "entity" = {
            "mappings" = {
              "identifier" = ".identifier"
              "title"      = ".title"
              "blueprint"  = "\"linearIssue\""
              "properties" = {
                "url"      = ".url"
                "status"   = ".state.name"
                "assignee" = ".assignee.email"
                "creator"  = ".creator.email"
                "priority" = ".priorityLabel"
                "created"  = ".createdAt"
                "updated"  = ".updatedAt"
              }
              "relations" = {
                "team"        = ".team.key"
                "labels"      = ".labelIds"
                "parentIssue" = ".parent.identifier"
              }
            }
          }
        }
      },
    ]
  })
}

resource "port_integration" "sonarqube_direct" {
  installation_id       = "sonarqube-direct"
  installation_app_type = "sonarqube"
  title                 = null
  config = jsonencode({
    "resources" = [
      {
        "kind" = "projects_ga"
        "selector" = {
          "query" = "true"
          "apiFilters" = {
            "qualifier" = [
              "TRK",
            ]
          }
          "metrics" = [
            "code_smells",
            "coverage",
            "bugs",
            "vulnerabilities",
            "duplicated_files",
            "security_hotspots",
            "new_violations",
            "new_coverage",
            "new_duplicated_lines_density",
          ]
        }
        "port" = {
          "entity" = {
            "mappings" = {
              "identifier" = ".key"
              "title"      = ".name"
              "blueprint"  = "\"sonarQubeProject\""
              "properties" = {
                "organization"            = ".organization"
                "link"                    = ".__link"
                "qualityGateStatus"       = ".__branch.status.qualityGateStatus"
                "lastAnalysisDate"        = "(.lastAnalysisDate // null) | if . then (.[:-2]) + \":\" + (.[-2:]) else null end"
                "numberOfBugs"            = ".__measures[]? | select(.metric == \"bugs\") | .value"
                "numberOfCodeSmells"      = ".__measures[]? | select(.metric == \"code_smells\") | .value"
                "numberOfVulnerabilities" = ".__measures[]? | select(.metric == \"vulnerabilities\") | .value"
                "numberOfHotSpots"        = ".__measures[]? | select(.metric == \"security_hotspots\") | .value"
                "numberOfDuplications"    = ".__measures[]? | select(.metric == \"duplicated_files\") | .value"
                "coverage"                = ".__measures[]? | select(.metric == \"coverage\") | .value"
                "mainBranch"              = ".__branch.name"
                "revision"                = ".revision"
                "managed"                 = ".managed"
              }
              "relations" = {
                "group" = "\"all_teams\""
              }
            }
          }
        }
      },
      {
        "kind" = "issues"
        "selector" = {
          "query" = "true"
          "apiFilters" = {
            "resolved" = "false"
          }
          "projectApiFilters" = {}
        }
        "port" = {
          "entity" = {
            "mappings" = {
              "identifier" = ".key"
              "title"      = ".message"
              "blueprint"  = "\"sonarQubeIssue\""
              "properties" = {
                "type"      = ".type"
                "severity"  = ".severity"
                "link"      = ".__link"
                "status"    = ".status"
                "assignees" = ".assignee"
                "tags"      = ".tags"
                "createdAt" = ".creationDate"
              }
              "relations" = {
                "sonarQubeProject" = ".project"
              }
            }
          }
        }
      },
    ]
    "deleteDependentEntities"      = true
    "createMissingRelatedEntities" = true
    "enableMergeEntity"            = true
  })
}


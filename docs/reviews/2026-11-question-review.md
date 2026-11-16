# Question review, November 2026

Every multiple-choice question was checked against the current official documentation (one reviewer per
certification). Each line names the question, what was wrong and the source used. Links were checked with
`scripts/check_links.py`. Glossary terms that were missing were added afterwards.

## KCNA

- kcna-fund-005: option b, the why for option a, and the explanation said Secrets are "base64-encoded in etcd". The docs say they are stored unencrypted in etcd; base64 is only how values look in manifests. Reworded. https://kubernetes.io/docs/concepts/configuration/secret/
- kcna-fund-017: the explanation listed IPVS as a normal kube-proxy mode. IPVS mode is deprecated since v1.35 (off by default from v1.40). https://kubernetes.io/docs/reference/networking/virtual-ips/
- kcna-fund-062: grammar ("Which component runs" changed to "Which components run", because the options list several components). No source needed.
- kcna-orch-001: docs link moved (/concepts/architecture/cri/ is now /concepts/containers/cri/). https://kubernetes.io/docs/concepts/containers/cri/
- kcna-orch-002, kcna-orch-020, kcna-orch-021, kcna-orch-042: probes docs link moved (configuration/liveness-readiness-startup-probes/ is now workloads/pods/probes/). https://kubernetes.io/docs/concepts/workloads/pods/probes/
- kcna-orch-030, kcna-arch-001: HPA docs link moved (tasks/run-application/ is now concepts/workloads/autoscaling/). https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/
- kcna-deliv-015: the link configuration/overview/#container-images now redirects to a 2025 blog post. Changed it to the Images concept page. https://kubernetes.io/docs/concepts/containers/images/
- kcna-deliv-018: the why said "Helm 3 keeps release history in Secrets". Helm 4 is now current, so it now says "Helm (since version 3)". https://helm.sh/docs/topics/chart_repository/

Reviewed 150 questions, changed 12

#### Not fixed
- kcna-arch-017 (cattle, not pets) and kcna-deliv-017 (feature flags) have `glossary: []`. No glossary term exists for "immutable infrastructure" or "feature flag". Suggest adding both to content/glossary.yaml and then linking them.

## KCSA

- kcsa-overview-014: The explanation said a cached private image can always be reused with IfNotPresent and no credentials. That is out of date. Since v1.35 the kubelet checks pull credentials for cached images by default (KubeletEnsureSecretPulledImages, beta, on by default), except for images pulled outside the kubelet. Explanation updated; the answer is unchanged. Source: https://kubernetes.io/docs/concepts/containers/images/ (section "Ensure image pull credential verification")
- kcsa-platform-009: Same outdated claim, in option b's why ("uses the cached image without contacting the registry") and in the explanation. Both updated, and the images docs link added; the answer is unchanged. Source: https://kubernetes.io/docs/concepts/containers/images/

Checked and no change needed: kube-proxy modes and default (iptables in v1.37; comp-015), PSA/PSS behaviour, the PSP removal in v1.25, ValidatingAdmissionPolicy GA in v1.30, and the AICPA SOC 2 link (it still resolves to the SOC suite page).

Not fixed: none.

Reviewed 120 questions, changed 2.

## TERRAFORM

#### Changed
- terraform-hcp-008: the why for "hard-mandatory" said it can never be overridden. A policy set can now allow overrides even for hard-mandatory failures. Reworded the why and the explanation, and changed the docs link from the moved Sentinel page to the page about enforcement levels. Source: https://developer.hashicorp.com/terraform/cloud-docs/policy-enforcement/manage-policy-sets
- terraform-hcp-016: the docs link cli/cloud/migrating no longer exists (it now redirects to the cloud block settings page). Replaced it with https://developer.hashicorp.com/terraform/cli/cloud/settings and kept https://developer.hashicorp.com/terraform/cloud-docs/migrate
- terraform-state-014: option text said `destroy = false`. The real syntax is `lifecycle { destroy = false }` inside the removed block. Source: https://developer.hashicorp.com/terraform/language/block/removed
- terraform-mod-001, mod-002, mod-003, mod-004, mod-005, mod-015: the docs link language/modules/sources now redirects to a general page that does not cover `//` subdirectories or the full source rules. Changed it to https://developer.hashicorp.com/terraform/language/block/module#source
- terraform-hcp-001, hcp-002, hcp-003, hcp-004: the cloud-docs/run/* links moved. Changed them to https://developer.hashicorp.com/terraform/cloud-docs/workspaces/run/(ui|cli|api|remote-operations)
- terraform-hcp-012: the cloud-docs/workspaces/variables links moved. Changed them to https://developer.hashicorp.com/terraform/cloud-docs/variables (and /variables/managing-variables)
- terraform-fund-008, fund-010, fund-011, fund-012: the language/providers/configuration link moved. Changed it to https://developer.hashicorp.com/terraform/language/block/provider
- terraform-fund-016, state-003: the language/state/sensitive-data link moved. Changed it to https://developer.hashicorp.com/terraform/language/manage-sensitive-data
- terraform-flow-014: the language/resources/behavior link moved. Changed it to https://developer.hashicorp.com/terraform/language/resources

Checked and still correct (no change needed): S3 `use_lockfile` and the deprecated `dynamodb_table` (https://developer.hashicorp.com/terraform/language/backend/s3); lifecycle arguments accept only literal values (https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle); import blocks, -generate-config-out, ephemeral values and write-only arguments, the cloud block, Explorer and change requests. All 89 docs URLs return HTTP 200.

Reviewed 152 questions, changed 21

#### Not fixed
- terraform-config-020 has `glossary: []`. No glossary term covers Terraform functions. A `tf-function` term would need to be added to content/glossary.d/terraform.yaml (outside my files).
- Not added: questions on the newer "Terraform policy" type (Advisory / Mandatory overridable / Mandatory), which now appears in HCP Terraform beside Sentinel and OPA. This is new content for later, not an error in the current questions.

## LFCS

- lfcs-net-010: the explanation said "Ubuntu uses systemd-timesyncd", but the linked Ubuntu page now says chrony is the default since 25.10. I limited the timesyncd claim to 24.04 and added the 25.10 change. Docs URL moved too. Source: https://ubuntu.com/server/docs/explanation/networking/about-time-synchronisation/
- lfcs-stor-004: "XFS cannot shrink" and "xfs_growfs can only grow, a smaller size is refused" are out of date. xfs_growfs -D now has limited, experimental shrinking. I reworded the answer, the why for d and the explanation. Source: https://manpages.ubuntu.com/manpages/noble/man8/xfs_growfs.8.html
- lfcs-stor-001: option d was ambiguous, because its own why admitted that vgcreate can create the PV itself. I replaced it with a clearly wrong order (vgcreate with no PV). Source: https://manpages.ubuntu.com/manpages/noble/man8/lvm.8.html. Docs URL moved too.
- lfcs-net-003: the glossary id `coredns` (Kubernetes cluster DNS) was wrong for the host resolver. I changed it to `lx-nsswitch`.
- lfcs-stor-008: added a note to the explanation. fallocate works on ext4, but swapon may refuse fallocated files on some filesystems, so dd is the portable way. Source: https://manpages.ubuntu.com/manpages/noble/man8/swapon.8.html
- lfcs-ess-014, lfcs-users-008, lfcs-net-002, lfcs-net-014, lfcs-net-016, lfcs-ops-012, lfcs-stor-009: the docs links pointed to documentation.ubuntu.com/server/..., which now gives a 301 redirect to ubuntu.com/server/docs/... I updated them to the new URLs (each checked: 200, correct page title).

Checked and correct (no change): net-014 ssh.socket on 24.04 needs daemon-reload plus a restart of ssh.socket (Launchpad bug 2069041 and the default sshd_config comment); ops-018 Docker restart policies; ops-012 apt-key deprecated and Signed-By; net-002 netplan. All other links return 200. The gnu.org links return 403 to curl only, because they block bots.

Reviewed 80 questions, changed 12

#### Not fixed
- lfcs-net-014: the Ubuntu OpenSSH server page (ubuntu.com/server/docs/how-to/security/openssh-server/) does not mention ssh.socket or socket activation. I found no official Ubuntu doc page or man page about it to link instead, so the question still links that page and sshd_config(5).

## DCA

- dca-sec-001: explanation presented Docker Content Trust as current; DCT is being retired (Notary v1 at notary.docker.io shuts down 8 Dec 2026, Sigstore/Cosign or Notation recommended). Added note + docs link. https://docs.docker.com/engine/security/trust/ , https://docs.docker.com/retired/#docker-content-trust-dct
- dca-sec-002: same DCT retirement note added to explanation. https://docs.docker.com/retired/#docker-content-trust-dct
- dca-inst-012: "default storage driver" is outdated: since Engine 29, fresh installs default to the containerd image store (overlayfs snapshotter); overlay2 is the default *classic* driver. Reworded question and explanation; fixed devicemapper why (deprecated 18.09, removed 25) and aufs why (dangling "too", not independent for DOMC). https://docs.docker.com/engine/storage/drivers/select-storage-driver/ , https://docs.docker.com/engine/storage/containerd/ , https://docs.docker.com/engine/deprecated/
- dca-img-019: why of option d said image IDs are not registry content addresses; with the containerd store (Engine 29 default) the image ID is the manifest/index digest. Reworded: you cannot pull by a local ID on other hosts. https://docs.docker.com/engine/storage/containerd/
- dca-img-005: option b text "ADD with a URL ... for local files" was self-contradictory; now "Use ADD instead of COPY to copy local files". https://docs.docker.com/build/building/best-practices/#add-or-copy
- dca-img-016, dca-img-020: `registry:2` updated to the current `registry:3` image (CNCF Distribution v3). https://distribution.github.io/distribution/about/deploying/
- dca-stor-012: question said `docker system prune` removes "images"; it removes only dangling images by default (all unused with -a). https://docs.docker.com/reference/cli/docker/system/prune/
- dca-net-003, dca-net-009: removed glossary id `coredns` (defined as the Kubernetes cluster DNS) from Docker embedded-DNS questions; misleading term. https://docs.docker.com/engine/network/#dns-services

All 156 doc URLs checked: no 404s, no redirects except docs.mirantis.com/mke/3.8/ -> overview.html (fine); all #anchors exist on their pages.

Reviewed 120 questions, changed 10

#### Not fixed
- content/glossary.yaml: there is no glossary term for Docker's embedded DNS server (127.0.0.11); a `docker-embedded-dns` term (certs: [dca]) would help net-003/net-009. `coredns` matches the plain word "DNS" globally, so it is still auto-highlighted in Docker questions with a Kubernetes definition.
- content/glossary.d/docker.yaml `content-trust` definition describes DCT as current; it should mention that DCT is being retired (Notary v1 shuts down 8 Dec 2026).

## GHA

- gha-act-002: said `node20` is a valid JavaScript runtime; Node 20 was removed from runners in Sept 2026. Now only `node24`, with a note to migrate. https://github.blog/changelog/2026-09-23-node-20-is-no-longer-available-in-github-actions
- gha-use-009: the list of GITHUB_TOKEN exceptions was incomplete. Docs now also list `pull_request` opened/synchronize/reopened events, which create runs that need approval. Updated the explanation and the why. https://docs.github.com/en/actions/concepts/security/github_token
- gha-sec-004: "expires after 24 hours at most" was not exact. The limit is 6 h on GitHub-hosted runners (job limit) and 24 h on self-hosted runners. https://docs.github.com/en/actions/concepts/security/github_token
- gha-ent-001: the explanation said enterprise accounts can share Actions secrets. The docs list only organization, repository and environment levels. Removed it. https://docs.github.com/en/actions/concepts/security/secrets
- gha-wf-021: the explanation said a group always has "one pending" run. There is a new `queue: single|max` option (max = 100 pending, and it cannot be combined with cancel-in-progress). Explanation updated. https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
- gha-use-016: the answer said admins can only make retention shorter. Private repos allow 1-400 days. Answer text is now "change", and the explanation gives the ranges. https://docs.github.com/en/organizations/managing-organization-settings/configuring-the-retention-period-for-github-actions-artifacts-and-logs-in-your-organization
- gha-use-017: the example put `runs-on`/`timeout-minutes` under the job key `defaults`, which is invalid workflow syntax. Rewrote it as an `env` mapping anchor/alias. https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations
- gha-wf-022: the docs link `.../reusable-workflows` redirects. It now points to `.../reusing-workflow-configurations`.
- gha-act-016: the immutable releases link had moved. It now points to https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases

Also checked and still correct: runner labels (ubuntu-latest=24.04, windows-latest=2025, ubuntu-20.04 retired), reusable workflow limits (10 levels / 50 workflows), SHA-pinning policy, cache rules (7 days, 10 GB, branch scope), Marketplace and policy rules. All 79 docs links return 200.

Reviewed 100 questions, changed 9.

#### Not fixed
- None.

## CAPA

- capa-cd-030: option d used the label `argocd.argoproj.io/instance` and said it "tracks which app owns a resource". Since Argo CD 3.0 the default tracking method is the annotation `argocd.argoproj.io/tracking-id`, and that label is only an example of a custom label. Changed the option to the tracking-id annotation, updated the why, and added a resource tracking docs link. https://argo-cd.readthedocs.io/en/stable/user-guide/resource_tracking/
- capa-cd-017: the explanation left out the `PreDelete` hook type (now in the docs). The docs link pointed to `resource_hooks/`, which now only says "This page has moved". Added PreDelete and moved the link to sync-waves. https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
- capa-cd-018: the docs link pointed to the moved `resource_hooks/` page. Changed it to sync-waves. https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
- capa-cd-005: the why of option c was an unfinished sentence ("but for Applications"). Rewrote it in plain English. (English only)
- capa-wf-033: the explanation used the single `mutex` / `semaphore` fields. These were removed in Argo Workflows v4.0; the fields are now the lists `mutexes` and `semaphores` under `synchronization`. Updated the explanation and added the deprecations link. https://argo-workflows.readthedocs.io/en/latest/deprecations/

Checked, no change needed: polling interval 120s + 60s jitter, auto-sync prune/selfHeal/no retry for the same commit/no rollback with auto-sync, default hook delete policy BeforeHookCreation, sync order phase > wave > kind > name, helm hook-weight mapped to sync-wave, Helm precedence (parameters highest), CronWorkflow `schedules` (list), Rollouts traffic routers and metric providers, EventBus types (NATS Streaming, JetStream, Kafka). All docs links return 200; only `resource_hooks/` was a "moved" stub.

Reviewed 100 questions, changed 5

#### Not fixed
- None.

## PCA

- pca-fund-007: the `why` for option d said Prometheus never watches prometheus.yml. Current versions have an optional `--config.auto-reload` flag (it checks every 30s by default). Fixed the why, added a note to the explanation and added the CLI docs link. https://prometheus.io/docs/prometheus/latest/command-line/prometheus/
- pca-fund-013: the correct answer used `--storage.tsdb.retention.time`. That flag is now DEPRECATED; retention is set in prometheus.yml under `storage.tsdb.retention.time` / `.size`. Fixed the answer text, the whys of a and c, and the explanation, and added a config docs link. https://prometheus.io/docs/prometheus/latest/configuration/configuration/#tsdb
- pca-fund-017: the docs link pointed to feature_flags, which no longer covers agent mode (it is now the stable `--agent` flag). Replaced it with the Agent Mode page. https://prometheus.io/docs/prometheus/latest/prometheus_agent/
- pca-inst-006: the why for the dotted name said dots are not used. Since 3.0, names may use any UTF-8 character, and the docs recommend `[a-zA-Z_:][a-zA-Z0-9_:]*`. Fixed the why. https://prometheus.io/docs/concepts/data_model/
- pca-inst-016: the why for b said native histograms are sent with "new text formats". The text format does not support them; scraping is protobuf plus `scrape_native_histograms`. The explanation now says they are stable since 3.8. https://prometheus.io/docs/specs/native_histograms/
- pca-promql-002: the explanation now says range selectors are left-open since Prometheus 3.0. https://prometheus.io/docs/prometheus/latest/querying/basics/#range-vector-selectors
- pca-obs-017: the explanation now names the OTLP receiver flag `--web.enable-otlp-receiver`. https://prometheus.io/docs/prometheus/latest/command-line/prometheus/

Reviewed 100 questions, changed 7

#### Not fixed
- None.

## SAA

- saa-cost-009: Answer was Snowball Edge, but AWS Snowball Edge is no longer available to new customers. The scenario now says the company already uses Snowball Edge, and the explanation names AWS Data Transfer Terminal for new customers (Snow Family is still in the exam guide). https://docs.aws.amazon.com/snowball/latest/developer-guide/whatisedge.html
- saa-perf-025: The explanation said "up to several secondary Regions". Aurora Global Database now supports up to 10. https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html
- saa-perf-030: The why for option d said "API Gateway still times out first". That is not always true, because the REST API integration timeout can now be raised. It now says the load on the backend stays the same. https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-caching.html
- saa-perf-036: Amazon QuickSight is now Quick Sight, part of Amazon Quick (the exam guide lists "Amazon Quick"). The option and explanation now use the new name and mention the old one. https://docs.aws.amazon.com/quicksight/latest/user/welcome.html
- saa-res-008: The explanation said a dead-letter queue does not include error details. It does: RequestID, ErrorCode and ErrorMessage are sent as message attributes. Only destinations include the full invocation record with the response. https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-retain-records.html
- saa-res-016: The why for option c said PITR restores only into the same Region. DynamoDB PITR supports cross-Region restore. https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Point-in-time-recovery.html
- saa-res-029: The glossary listed aws-api-gateway, which has nothing to do with this question. Changed to [aws-ec2, aws-region]. https://docs.aws.amazon.com/sdkref/latest/guide/feature-retry-behavior.html
- saa-sec-012: The answer needed the ALB rule (option a), but the question only stated a database requirement, so option a did not follow from it. The question now also says users must reach the app over HTTPS through the ALB. https://docs.aws.amazon.com/vpc/latest/userguide/security-group-rules.html

Reviewed 150 questions, changed 8

#### Not fixed
- The glossary has no term for service quotas, throttling or retry with exponential backoff (needed for saa-res-029). Suggested new term in content/glossary.d: `aws-service-quotas`.
- The glossary has no terms for AWS Batch, Amazon Inspector, Amazon EMR, AWS Lake Formation or Amazon Quick. Questions saa-perf-013, saa-sec-021, saa-perf-035 and saa-perf-036 would benefit from them.

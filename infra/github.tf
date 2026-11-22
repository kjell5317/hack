locals {
  github_owner = split("/", var.github_repository)[0]
  github_repo  = split("/", var.github_repository)[1]

  # --- PROD_ENV: the repo's .env minus local Supabase values, plus the hosted ones ---

  env_file = coalesce(var.env_file, "${path.module}/../.env")
  # BOM and \r stripped so files saved on Windows parse the same.
  env_text = replace(trimprefix(fileexists(local.env_file) ? file(local.env_file) : "", "\uFEFF"), "\r", "")
  # KEY=value, optionally prefixed with `export`; split on the first `=` only.
  # Blank lines, # comments and anything else that isn't an assignment are skipped.
  env_line_pattern = "^\\s*(?:export\\s+)?([A-Za-z_][A-Za-z0-9_]*)\\s*=(.*)$"
  env_pairs = [
    for line in split("\n", local.env_text) : regex(local.env_line_pattern, line)
    if can(regex(local.env_line_pattern, line))
  ]
  # `...` groups repeated keys instead of erroring; the last assignment wins.
  env_grouped = { for p in local.env_pairs : p[0] => trimspace(p[1])... }
  env_from_file = {
    for k, values in local.env_grouped : k => values[length(values) - 1]
    if values[length(values) - 1] != "" && !startswith(k, "SUPABASE_")
  }

  prod_env = merge(local.env_from_file, {
    SUPABASE_URL                 = local.supabase_url
    SUPABASE_PUBLISHABLE_KEY     = local.supabase_publishable_key
    SUPABASE_SECRET_KEY          = local.supabase_secret_key
    LANGFUSE_TRACING_ENVIRONMENT = "production"
  })
  # Maps iterate in lexical key order, so the lines come out sorted.
  prod_env_dotenv = sensitive(join("", [for k, v in local.prod_env : "${k}=${v}\n"]))
}

# --- Actions variables (read by .github/workflows/ci.yml) ---

# DEMO_DOMAIN switches on the images and deploy jobs in CI, so it's created
# last: if an earlier step fails, pushes to main keep passing instead of
# running a deploy that lacks its secrets.
resource "github_actions_variable" "demo_domain" {
  repository    = local.github_repo
  variable_name = "DEMO_DOMAIN"
  value         = local.fqdn

  depends_on = [
    github_actions_secret.deploy_ssh_key,
    github_actions_secret.supabase_access_token,
    github_actions_secret.supabase_db_password,
    github_actions_secret.prod_env,
    github_actions_variable.supabase_project_ref,
    github_actions_variable.deploy_host,
    cloudflare_dns_record.demo,
  ]
}

resource "github_actions_variable" "supabase_project_ref" {
  repository    = local.github_repo
  variable_name = "SUPABASE_PROJECT_REF"
  value         = supabase_project.this.id
}

# A proxied record hides the server, so CI needs its IP to SSH in.
resource "github_actions_variable" "deploy_host" {
  count = var.cloudflare_proxied ? 1 : 0

  repository    = local.github_repo
  variable_name = "DEPLOY_HOST"
  value         = hcloud_server.demo.ipv4_address
}

# --- Actions secrets ---

resource "github_actions_secret" "deploy_ssh_key" {
  repository  = local.github_repo
  secret_name = "DEPLOY_SSH_KEY"
  value       = tls_private_key.deploy.private_key_openssh
}

resource "github_actions_secret" "supabase_access_token" {
  repository  = local.github_repo
  secret_name = "SUPABASE_ACCESS_TOKEN"
  value       = var.supabase_access_token
}

resource "github_actions_secret" "supabase_db_password" {
  repository  = local.github_repo
  secret_name = "SUPABASE_DB_PASSWORD"
  value       = random_password.supabase_db.result
}

resource "github_actions_secret" "prod_env" {
  repository  = local.github_repo
  secret_name = "PROD_ENV"
  value       = local.prod_env_dotenv
}

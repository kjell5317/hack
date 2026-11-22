resource "random_password" "supabase_db" {
  length  = 32
  special = false # alphanumeric: safe in connection strings and shells
}

resource "supabase_project" "this" {
  organization_id   = var.supabase_organization_id
  name              = var.name
  database_password = random_password.supabase_db.result
  region            = var.supabase_region

  # Create polls until the project reports ACTIVE_HEALTHY. The provider's
  # default 5m is tight for a fresh project.
  timeouts {
    create = "15m"
  }
}

# Auth for the deployed site. Create/update first waits until every project
# service (auth, db, rest, storage, ...) reports healthy.
resource "supabase_settings" "this" {
  project_ref = supabase_project.this.id

  auth = jsonencode({
    site_url       = "https://${local.fqdn}"
    uri_allow_list = "https://${local.fqdn}/**"
    # Hosted Supabase's built-in SMTP only mails project members (~2/hour),
    # so judges could never confirm a sign-up without custom SMTP.
    mailer_autoconfirm = !var.auth_email_confirmation
  })

  timeouts {
    create = "15m"
    update = "15m"
  }
}

data "supabase_apikeys" "this" {
  project_ref = supabase_project.this.id

  # Read the keys only once supabase_settings has seen all services healthy.
  depends_on = [supabase_settings.this]

  lifecycle {
    postcondition {
      condition = alltrue([
        try(coalesce(self.publishable_key, self.anon_key), "") != "",
        try(coalesce(try(self.secret_keys[0].api_key, null), self.service_role_key), "") != "",
      ])
      error_message = "The Supabase API returned no publishable/anon or secret/service_role key for this project."
    }
  }
}

locals {
  supabase_url = "https://${supabase_project.this.id}.supabase.co"

  # New publishable/secret keys when the project has them, legacy JWT keys
  # otherwise (backend and frontend accept both).
  supabase_publishable_key = coalesce(
    data.supabase_apikeys.this.publishable_key,
    data.supabase_apikeys.this.anon_key,
  )
  supabase_secret_key = coalesce(
    try([for k in data.supabase_apikeys.this.secret_keys : k.api_key if k.name == "default"][0], null),
    try(data.supabase_apikeys.this.secret_keys[0].api_key, null),
    data.supabase_apikeys.this.service_role_key,
  )
}

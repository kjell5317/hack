variable "name" {
  description = "Prefix for Hetzner resource names; also the Supabase project name."
  type        = string
  default     = "hack"
}

# --- Credentials ---

variable "hcloud_token" {
  description = "Hetzner Cloud API token (Read & Write). Null falls back to the HCLOUD_TOKEN env var."
  type        = string
  sensitive   = true
  default     = null
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with Zone:DNS:Edit and Zone:Read on the zone. Null falls back to the CLOUDFLARE_API_TOKEN env var."
  type        = string
  sensitive   = true
  default     = null
}

variable "supabase_access_token" {
  description = "Supabase personal access token (supabase.com/dashboard/account/tokens). Also uploaded as the SUPABASE_ACCESS_TOKEN GitHub secret so CI can run migrations."
  type        = string
  sensitive   = true

  validation {
    condition     = trimspace(var.supabase_access_token) != ""
    error_message = "Set supabase_access_token (terraform.tfvars or TF_VAR_supabase_access_token)."
  }
}

# --- Supabase ---

variable "supabase_organization_id" {
  description = "Supabase organization slug, the <slug> in supabase.com/dashboard/org/<slug>."
  type        = string

  validation {
    condition     = trimspace(var.supabase_organization_id) != ""
    error_message = "Set supabase_organization_id to the org slug from the dashboard URL."
  }
}

variable "supabase_region" {
  description = "Supabase region code, e.g. eu-central-1 (Frankfurt), us-east-1."
  type        = string
  default     = "eu-central-1"
}

variable "auth_email_confirmation" {
  description = "Require users to confirm their email before signing in. Off by default: hosted Supabase's built-in SMTP only mails project members (about 2 mails/hour), so without your own SMTP nobody else could sign up."
  type        = bool
  default     = false
}

# --- GitHub ---

variable "github_repository" {
  description = "Repository whose Actions secrets and variables are managed, as \"owner/name\"."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", var.github_repository))
    error_message = "github_repository must look like \"owner/name\"."
  }
}

variable "env_file" {
  description = "dotenv file whose non-empty, non-SUPABASE_* keys go into the PROD_ENV secret. Null means the repo root .env (path.module/../.env). A missing file counts as empty."
  type        = string
  default     = null
}

# --- DNS and server ---

variable "cloudflare_zone" {
  description = "Cloudflare zone (apex domain), e.g. example.com."
  type        = string
}

variable "subdomain" {
  description = "Record name inside the zone, e.g. \"demo\" for demo.example.com."
  type        = string
}

variable "cloudflare_proxied" {
  description = "Route traffic through Cloudflare's proxy. Keep false unless you know you need it: SSH to the hostname and Caddy's certificate issuance assume a direct record. When true, CI deploys to the server IP via the DEPLOY_HOST variable."
  type        = bool
  default     = false
}

variable "server_type" {
  description = "Hetzner server type. Cost-optimized types (cx*) are sometimes sold out; cpx22 is a fallback."
  type        = string
  default     = "cx23"
}

variable "location" {
  description = "Hetzner location: nbg1, fsn1, hel1, ash, hil, sin."
  type        = string
  default     = "nbg1"
}

variable "ssh_public_key_files" {
  description = "Public keys that may SSH in as root, in addition to the generated CI deploy key. Files that don't exist on this machine are skipped."
  type        = list(string)
  default     = ["~/.ssh/id_ed25519.pub"]
}

variable "ssh_allowed_cidrs" {
  description = "Sources allowed to reach SSH. GitHub-hosted runners have no fixed IPs, so this is open by default."
  type        = list(string)
  default     = ["0.0.0.0/0", "::/0"]
}

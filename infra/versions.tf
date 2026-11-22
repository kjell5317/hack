terraform {
  required_version = ">= 1.6"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.70"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.28"
    }
    supabase = {
      source  = "supabase/supabase"
      version = "~> 1.11"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.13"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.4"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9"
    }
  }
}

# An unset (or empty) token falls back to HCLOUD_TOKEN / CLOUDFLARE_API_TOKEN.
provider "hcloud" {
  token = var.hcloud_token == "" ? null : var.hcloud_token
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token == "" ? null : var.cloudflare_api_token
}

provider "supabase" {
  access_token = var.supabase_access_token
}

# Token from GITHUB_TOKEN; if that is unset the provider runs `gh auth token`.
provider "github" {
  owner = local.github_owner
}

variable "name" {
  description = "Prefix for Hetzner resource names."
  type        = string
  default     = "hack"
}

variable "cloudflare_zone" {
  description = "Cloudflare zone (apex domain), e.g. example.com."
  type        = string
}

variable "subdomain" {
  description = "Record name inside the zone, e.g. \"demo\" for demo.example.com."
  type        = string
}

variable "cloudflare_proxied" {
  description = "Route traffic through Cloudflare's proxy. Keep false unless you know you need it: SSH to the hostname and Caddy's certificate issuance assume a direct record."
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
  description = "Public keys that may SSH in as root, in addition to the generated CI deploy key."
  type        = list(string)
  default     = ["~/.ssh/id_ed25519.pub"]
}

variable "ssh_allowed_cidrs" {
  description = "Sources allowed to reach SSH. GitHub-hosted runners have no fixed IPs, so this is open by default."
  type        = list(string)
  default     = ["0.0.0.0/0", "::/0"]
}

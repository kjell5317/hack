locals {
  fqdn = "${var.subdomain}.${var.cloudflare_zone}"
}

# Key pair used by the GitHub Actions deploy job (`make gh-setup` uploads it).
resource "tls_private_key" "deploy" {
  algorithm = "ED25519"
}

resource "hcloud_ssh_key" "deploy" {
  name       = "${var.name}-deploy"
  public_key = tls_private_key.deploy.public_key_openssh
}

resource "hcloud_firewall" "demo" {
  name = "${var.name}-demo"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = var.ssh_allowed_cidrs
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "udp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "icmp"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_server" "demo" {
  name         = "${var.name}-demo"
  server_type  = var.server_type
  image        = "ubuntu-24.04"
  location     = var.location
  ssh_keys     = [hcloud_ssh_key.deploy.id]
  firewall_ids = [hcloud_firewall.demo.id]

  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    admin_keys = [for f in var.ssh_public_key_files : trimspace(file(pathexpand(f)))]
  })

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  labels = {
    app = var.name
  }

  # user_data changes would force a new server (new IP, new certificate).
  lifecycle {
    ignore_changes = [user_data]
  }
}

data "cloudflare_zone" "this" {
  filter = {
    name = var.cloudflare_zone
  }
}

resource "cloudflare_dns_record" "demo" {
  zone_id = data.cloudflare_zone.this.id
  name    = local.fqdn
  type    = "A"
  content = hcloud_server.demo.ipv4_address
  ttl     = 1 # automatic
  proxied = var.cloudflare_proxied
  comment = "Managed by Terraform (${var.name})"
}

output "ipv4" {
  value = hcloud_server.demo.ipv4_address
}

output "domain" {
  value = local.fqdn
}

output "url" {
  value = "https://${local.fqdn}"
}

output "ssh" {
  value = "ssh root@${hcloud_server.demo.ipv4_address}"
}

output "deploy_private_key" {
  description = "Private key for the DEPLOY_SSH_KEY GitHub secret."
  value       = tls_private_key.deploy.private_key_openssh
  sensitive   = true
}

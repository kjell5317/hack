output "url" {
  value = "https://${local.fqdn}"
}

output "domain" {
  value = local.fqdn
}

output "ipv4" {
  value = hcloud_server.demo.ipv4_address
}

output "ssh" {
  value = "ssh root@${hcloud_server.demo.ipv4_address}"
}

output "supabase_project_ref" {
  value = supabase_project.this.id
}

output "supabase_dashboard_url" {
  value = "https://supabase.com/dashboard/project/${supabase_project.this.id}"
}

output "deploy_private_key" {
  description = "Private key of the CI deploy key pair (already uploaded as the DEPLOY_SSH_KEY GitHub secret)."
  value       = tls_private_key.deploy.private_key_openssh
  sensitive   = true
}

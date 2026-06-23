# OpenTofu — Proxmox lane (B58 IaC, lane b). Manages the weyland VMs/CTs via the bpg/proxmox provider.
# State in MinIO (separate key from the port lane). Brownfield: `tofu import` the live guests, PLAN-ONLY first —
# never apply a destructive diff to a running VM. NO secrets committed — all via env:
#   AWS_ACCESS_KEY_ID=admin  AWS_SECRET_ACCESS_KEY=weyland_dev_password   (MinIO, for the state backend)
#   PROXMOX_VE_ENDPOINT='https://weyland:8006/'                          (Proxmox API)
#   PROXMOX_VE_API_TOKEN='root@pam!tofu=<secret-uuid>'                   (Proxmox API token)
terraform {
  required_version = ">= 1.6"

  required_providers {
    proxmox = {
      source = "bpg/proxmox"   # version unpinned for the first init; pin to whatever it installs (see lock file)
    }
  }

  backend "s3" {
    endpoints                   = { s3 = "https://s3.weyland.lab" }
    bucket                      = "tofu-state"
    key                         = "proxmox/terraform.tfstate"
    region                      = "us-east-1"
    use_path_style              = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_s3_checksum            = true
  }
}

provider "proxmox" {
  insecure = true   # Proxmox ships a self-signed cert; endpoint + api_token come from env (PROXMOX_VE_*).
}

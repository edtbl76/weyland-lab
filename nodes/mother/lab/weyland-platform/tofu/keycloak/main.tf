# OpenTofu — Keycloak lane (B1.1 Phase 2). Codifies the `weyland` realm + OIDC clients (SSO config as code).
# State in MinIO (own key). Runs from rogueone against the live Keycloak. NO secrets committed — all via env:
#   AWS_ACCESS_KEY_ID=admin  AWS_SECRET_ACCESS_KEY=weyland_dev_password   (MinIO, state backend)
#   TF_VAR_kc_admin_password=weyland_dev_password                        (Keycloak bootstrap admin)
#   TF_VAR_operator_password=weyland_dev_password                        (your realm user)
terraform {
  required_version = ">= 1.6"

  required_providers {
    keycloak = {
      # Community-maintained successor to the archived mrparkers/keycloak. If `tofu init` can't
      # resolve this, swap to source = "mrparkers/keycloak", version = "~> 4.4" — same resource schema.
      source  = "keycloak/keycloak"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    endpoints                   = { s3 = "https://s3.weyland.lab" }
    bucket                      = "tofu-state"
    key                         = "keycloak/terraform.tfstate"
    region                      = "us-east-1"
    use_path_style              = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_s3_checksum            = true
  }
}

provider "keycloak" {
  client_id = "admin-cli"
  username  = var.kc_admin_username
  password  = var.kc_admin_password
  url       = "https://keycloak.weyland.lab"
  # TLS verified against rogueone's system trust store — the mkcert root is installed there (it's how you
  # browse *.weyland.lab). If `tofu plan` ever throws an x509 "unknown authority" error, run `mkcert -install`
  # on rogueone to (re)add the root to the system store.
}

variable "kc_admin_username" {
  type    = string
  default = "admin"
}

variable "kc_admin_password" {
  type      = string
  sensitive = true
}

variable "operator_password" {
  type      = string
  sensitive = true
}

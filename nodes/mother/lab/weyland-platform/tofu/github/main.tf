# OpenTofu — GitHub lane (B58 IaC, lane b). Codifies the weyland-lab repo (settings, branch protection, webhooks).
# State in MinIO (own key). Brownfield: import the live repo. NO secrets committed — all via env:
#   AWS_ACCESS_KEY_ID=admin  AWS_SECRET_ACCESS_KEY=weyland_dev_password   (MinIO, for the state backend)
#   GITHUB_TOKEN=ghp_...                                                  (GitHub PAT — repo scope)
terraform {
  required_version = ">= 1.6"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    endpoints                   = { s3 = "https://s3.weyland.lab" }
    bucket                      = "tofu-state"
    key                         = "github/terraform.tfstate"
    region                      = "us-east-1"
    use_path_style              = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_s3_checksum            = true
  }
}

provider "github" {
  owner = "edtbl76"   # token from env GITHUB_TOKEN
}

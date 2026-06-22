# OpenTofu — Port lane (B58 IaC, lane b). Codifies the Port catalog config (the blueprints/dashboards built via
# MCP) as declarative IaC. State lives in MinIO (S3 backend at s3.weyland.lab). Brownfield: `tofu import` each
# existing resource, then refine HCL until `tofu plan` is clean. NO secrets committed — all via env:
#   AWS_ACCESS_KEY_ID=admin  AWS_SECRET_ACCESS_KEY=weyland_dev_password   (MinIO, for the state backend)
#   PORT_CLIENT_ID=...       PORT_CLIENT_SECRET=...                       (Port API, for the provider)
terraform {
  required_version = ">= 1.6"

  required_providers {
    port = {
      source  = "port-labs/port-labs"
      version = "~> 2.0"
    }
  }

  backend "s3" {
    endpoints                   = { s3 = "https://s3.weyland.lab" }
    bucket                      = "tofu-state"
    key                         = "port/terraform.tfstate"
    region                      = "us-east-1"
    use_path_style              = true   # MinIO requires path-style addressing
    skip_credentials_validation = true   # the AWS-isms below don't apply to MinIO
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_s3_checksum            = true   # MinIO chokes on the newer AWS checksum trailers
  }
}

provider "port" {
  # client_id / secret read from env (PORT_CLIENT_ID / PORT_CLIENT_SECRET).
  # EU org (org_KyCTEN4PVUv1D3TM): default base_url https://api.getport.io routes by org token; adjust here if auth fails.
}

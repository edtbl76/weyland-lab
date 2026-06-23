# ollama — LXC CT 102 (Ollama CPU LLM serving). Codified from the live guest via -generate-config-out, with the
# two generator-emitted invalid sentinels dropped: cpu.units = 0 (must be 1-500000) and
# initialization.entrypoint = "" (empty disallowed) — both default cleanly when omitted. Imported, not created.
resource "proxmox_virtual_environment_container" "ollama" {
  description           = ""
  environment_variables = {}
  hook_script_file_id   = ""
  node_name             = "weyland"
  pool_id               = null
  protection            = false
  start_on_boot         = true
  started               = true
  tags                  = []
  template              = false
  timeout_clone         = 1800
  timeout_create        = 1800
  timeout_delete        = 60
  timeout_start         = 300
  timeout_update        = 1800
  unprivileged          = true
  vm_id                 = null
  console {
    enabled   = true
    tty_count = 2
    type      = "tty"
  }
  cpu {
    architecture = "amd64"
    cores        = 14
    limit        = 0
  }
  disk {
    acl           = false
    datastore_id  = "local-zfs"
    mount_options = []
    quota         = false
    replicate     = false
    size          = 150
  }
  features {
    fuse    = false
    keyctl  = false
    mknod   = false
    mount   = []
    nesting = true
  }
  initialization {
    hostname = "ollama"
    ip_config {
      ipv4 {
        address = "dhcp"
        gateway = ""
      }
    }
  }
  memory {
    dedicated = 49152
    swap      = 0
  }
  network_interface {
    bridge       = "vmbr0"
    enabled      = true
    firewall     = false
    host_managed = false
    mac_address  = "BC:24:11:B4:25:03"
    mtu          = 0
    name         = "eth0"
    rate_limit   = 0
    vlan_id      = 0
  }
  operating_system {
    template_file_id = ""
    type             = "debian"
  }
}

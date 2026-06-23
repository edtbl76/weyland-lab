# whisper — LXC CT 103 (whisper.cpp CPU STT serving). Codified from the live guest; bpg sentinels dropped
# (cpu.units=0, initialization.entrypoint="") + timeouts pinned to provider defaults. Imported, not created.
resource "proxmox_virtual_environment_container" "whisper" {
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
    cores        = 8
    limit        = 0
  }
  disk {
    acl           = false
    datastore_id  = "local-zfs"
    mount_options = []
    quota         = false
    replicate     = false
    size          = 15
  }
  features {
    fuse    = false
    keyctl  = false
    mknod   = false
    mount   = []
    nesting = true
  }
  initialization {
    hostname = "whisper"
    ip_config {
      ipv4 {
        address = "dhcp"
        gateway = ""
      }
    }
  }
  memory {
    dedicated = 8192
    swap      = 0
  }
  network_interface {
    bridge       = "vmbr0"
    enabled      = true
    firewall     = false
    host_managed = false
    mac_address  = "BC:24:11:44:54:81"
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

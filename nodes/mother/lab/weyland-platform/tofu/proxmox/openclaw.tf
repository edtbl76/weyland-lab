# openclaw — VM 100 (agent control plane: Docker OpenClaw + Telegram bot). Codified from the live guest; dropped
# the bpg sentinels (cpu.units=0, cpu.architecture="") + the computed top-level mac_addresses list. Imported.
resource "proxmox_virtual_environment_vm" "openclaw" {
  acpi                                 = true
  bios                                 = "ovmf"
  boot_order                           = ["virtio0", "ide2", "net0"]
  delete_unreferenced_disks_on_destroy = true
  description                          = "192.168.1.169"
  hook_script_file_id                  = ""
  hotplug                              = null
  keyboard_layout                      = "en-us"
  kvm_arguments                        = ""
  machine                              = "q35"
  migrate                              = false
  name                                 = "openclaw"
  network_device = [{
    bridge       = "vmbr0"
    disconnected = false
    enabled      = true
    firewall     = true
    mac_address  = "BC:24:11:9D:6B:2F"
    model        = "virtio"
    mtu          = 0
    queues       = 0
    rate_limit   = 0
    trunks       = ""
    vlan_id      = 0
  }]
  node_name           = "weyland"
  on_boot             = false
  pool_id             = ""
  protection          = false
  purge_on_destroy    = true
  reboot              = false
  reboot_after_update = true
  scsi_hardware       = "virtio-scsi-single"
  started             = true
  stop_on_destroy     = false
  tablet_device       = true
  tags                = []
  template            = false
  timeout_clone       = 1800
  timeout_create      = 1800
  timeout_migrate     = 1800
  timeout_reboot      = 1800
  timeout_shutdown_vm = 1800
  timeout_start_vm    = 1800
  timeout_stop_vm     = 300
  vm_id               = 100
  agent {
    enabled = true
    timeout = "15m"
    trim    = false
    type    = "virtio"
  }
  cpu {
    cores      = 4
    flags      = []
    hotplugged = 0
    limit      = 0
    numa       = false
    sockets    = 1
    type       = "host"
  }
  disk {
    aio               = "io_uring"
    backup            = true
    cache             = "none"
    datastore_id      = "local-zfs"
    discard           = "ignore"
    file_format       = "raw"
    file_id           = ""
    import_from       = ""
    interface         = "virtio0"
    iothread          = true
    path_in_datastore = "vm-100-disk-1"
    queues            = 0
    replicate         = true
    serial            = ""
    size              = 80
    ssd               = false
  }
  efi_disk {
    datastore_id      = "local-zfs"
    file_format       = "raw"
    pre_enrolled_keys = true
    type              = "4m"
  }
  memory {
    dedicated      = 8192
    floating       = 0
    keep_hugepages = false
    shared         = 0
  }
  operating_system {
    type = "l26"
  }
}

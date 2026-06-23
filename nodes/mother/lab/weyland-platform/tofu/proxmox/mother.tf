# mother — VM 101 (the k3s AI platform). Codified from the live guest; same bpg sentinels dropped as openclaw
# (cpu.units/architecture/affinity, memory.hugepages, computed mac_addresses).
#
# DISKS ARE INTENTIONALLY UNMANAGED via lifecycle.ignore_changes — mother has a RAW PASSTHROUGH disk
# (/dev/disk/by-id/wwn-0x5000c500c67e302c-part1, the 4TB Seagate hosting MinIO/B6) that bpg can't round-trip
# cleanly (datastore_id/file_format are empty), plus the normal vm-101-disk-1 (200G local-zfs). For the critical
# platform VM we never want tofu reconfiguring storage, so the disks are adopted-as-is and frozen. efi_disk is
# clean and stays managed.
resource "proxmox_virtual_environment_vm" "mother" {
  acpi                                 = true
  bios                                 = "ovmf"
  boot_order                           = ["virtio0", "ide2", "net0"]
  delete_unreferenced_disks_on_destroy = true
  description                          = ""
  hook_script_file_id                  = ""
  hotplug                              = null
  keyboard_layout                      = "en-us"
  kvm_arguments                        = ""
  machine                              = "q35"
  migrate                              = false
  name                                 = "mother"
  network_device = [{
    bridge       = "vmbr0"
    disconnected = false
    enabled      = true
    firewall     = true
    mac_address  = "BC:24:11:D9:78:2C"
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
  vm_id               = 101
  cpu {
    cores      = 8
    flags      = []
    hotplugged = 0
    limit      = 0
    numa       = false
    sockets    = 1
    type       = "x86-64-v2-AES"
  }
  efi_disk {
    datastore_id      = "local-zfs"
    file_format       = "raw"
    pre_enrolled_keys = true
    type              = "4m"
  }
  memory {
    dedicated      = 32768
    floating       = 0
    keep_hugepages = false
    shared         = 0
  }
  operating_system {
    type = "l26"
  }
  lifecycle {
    ignore_changes = [disk]
  }
}

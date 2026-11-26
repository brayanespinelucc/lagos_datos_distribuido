"""Pruebas de configuraciones y salvaguardas. No requieren hipervisor ni discos."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROXMOX = ROOT / "infrastructure/proxmox"
sys.path.insert(0, str(PROXMOX))
import check_mesh
import provision

spec = importlib.util.spec_from_file_location("volumes", ROOT / "infrastructure/ubuntu/prepare_volumes.py")
volumes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(volumes)


class InfrastructureTests(unittest.TestCase):
    def setUp(self):
        self.data = provision.read_inventory()
        self.vms = self.data["vms"]
        self.minio = next(vm for vm in self.vms if vm["role"] == "minio")
        self.disk = self.minio["data_disks"][0]

    def test_eight_vms_six_data_volumes_56_directed_peers(self):
        plan = provision.plan(self.data)
        self.assertEqual(plan["totals"], {"vms": 8, "vcpus": 26, "memory_mib": 51200,
                                          "os_disk_gib": 260, "data_disk_gib": 120})
        pairs = {(vm["id"], p["id"]) for vm in self.vms for p in check_mesh.peers_for(self.vms, vm)}
        self.assertEqual(len(pairs), 56)
        self.assertFalse(any(x == y for x, y in pairs))

    def test_reject_overlapping_network_or_duplicate_vm(self):
        for key in ("pod_cidr", "service_cidr"):
            invalid = copy.deepcopy(self.data)
            invalid["network"][key] = invalid["network"]["cidr"]
            with self.assertRaises(ValueError):
                provision.validate_inventory(invalid)
        self.vms[1]["id"] = self.vms[0]["id"]
        with self.assertRaises(ValueError):
            provision.validate_inventory(self.data)

    def test_cloud_config_covers_hosts_ssh_ntp_disks(self):
        for vm in self.vms:
            text = provision.cloud_config(self.data, vm, "PUBLIC_TEST_VALUE")
            self.assertTrue(text.startswith("#cloud-config\n"))
            config = json.loads(text.split("\n", 1)[1])
            files = {f["path"]: f["content"] for f in config["write_files"]}
            self.assertEqual(config["users"][0]["ssh_authorized_keys"], ["PUBLIC_TEST_VALUE"])
            self.assertFalse(config["ssh_pwauth"])
            self.assertIn("PermitRootLogin no", files["/etc/ssh/sshd_config.d/00-lago-access.conf"])
            self.assertIn(["systemctl", "enable", "--now", "systemd-timesyncd"], config["runcmd"])
            for peer in self.vms:
                self.assertIn(peer["ip"] + " " + peer["hostname"] + ".", files["/etc/hosts"])
            self.assertEqual("/etc/lago/minio-disks.json" in files, vm["role"] == "minio")
            if vm["data_disks"]:
                self.assertEqual(json.loads(files["/etc/lago/minio-disks.json"]), vm["data_disks"])

    def test_inbound_rules_keep_console_and_overlay_scoped(self):
        fw = provision.firewall(self.data, self.minio)
        self.assertIn("policy_in: DROP", fw)
        self.assertIn("IN ACCEPT -source 10.42.10.10 -p tcp -dport 9001\n", fw)
        self.assertNotIn("IN ACCEPT -source 10.42.10.32 -p tcp -dport 9001", fw)
        self.assertNotIn("0.0.0.0/0", fw)
        worker = next(vm for vm in self.vms if vm["role"] == "rke2-worker")
        rules = provision.firewall(self.data, worker)
        self.assertIn("IN ACCEPT -source 10.42.10.31 -p udp -dport 8472\n", rules)
        self.assertNotIn("IN ACCEPT -source 10.42.10.21 -p udp -dport 8472", rules)

    def test_ssh_public_key_render_repeat_and_preserve_foreign_firewall(self):
        with tempfile.TemporaryDirectory() as tmp:
            key, out = Path(tmp, "ephemeral"), Path(tmp, "out")
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "test", "-f", str(key)], check=True)
            command = [sys.executable, str(PROXMOX / "provision.py"), "render", "--output", str(out), "--ssh-key", str(key)+".pub"]
            subprocess.run(command, check=True, capture_output=True)
            old = {p.name: p.read_bytes() for p in out.iterdir()}
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(old, {p.name: p.read_bytes() for p in out.iterdir()})
            self.assertEqual(len(old), 16)
            manual = out / f"{self.minio['id']}.fw"
            manual.write_text("manual\n")
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(manual.read_text(), "manual\n")
            with self.assertRaises(ValueError):
                provision.read_public_key(key)

    def test_does_not_adopt_an_existing_foreign_id(self):
        with self.assertRaisesRegex(ValueError, "ocupado"):
            provision.check_owned_vm({"description":"externo"}, self.data, self.minio, "propia", "local-lvm", "local:snippets/a")

    def test_guest_disk_must_be_unique_unmounted_expected_size_and_signature(self):
        disk = {"serial": self.disk["serial"], "size": 20*1024**3, "type": "disk", "ro": False, "rm": False,
                "path": "/dev/fixture", "mountpoints": [], "uuid": None, "pttype": None, "fstype": None, "label":None}
        self.assertEqual(volumes.matching_disk(self.disk, [disk]), disk)
        self.assertTrue(volumes.needs_format(self.disk, disk, set()))
        for mod in ({"serial":"ajeno"}, {"size":1024}, {"pttype":"gpt"}, {"mountpoints":["/"]},
                    {"ro":True}, {"children":[{"type":"part"}]}):
            with self.assertRaises(ValueError):
                volumes.matching_disk(self.disk, [dict(disk, **mod)])
        with self.assertRaises(ValueError):
            volumes.matching_disk(self.disk, [disk,disk])
        with self.assertRaises(ValueError):
            volumes.needs_format(self.disk, disk, {"ext4"})
        existing = dict(disk, fstype="xfs", label=self.disk["serial"], uuid="sample")
        self.assertFalse(volumes.needs_format(self.disk, existing, {"xfs"}))
        with self.assertRaises(ValueError):
            volumes.needs_format(self.disk, dict(existing, label="ajeno"), {"xfs"})

    def test_fstab_reuse_and_conflict(self):
        disk = {"path":"/dev/fixture","uuid":"sample"}
        mount = self.disk["mount"]
        entry = volumes.fstab_entry("", disk, mount)
        self.assertIn("UUID=sample", entry)
        self.assertEqual(volumes.fstab_entry(entry, disk, mount), "")
        for other in (entry.replace("sample", "otro"), entry.replace(mount, "/otra"), entry + entry):
            with self.assertRaises(ValueError):
                volumes.fstab_entry(other, disk, mount)

    def test_vm_command_maps_exact_disks_without_destroy(self):
        args = provision.vm_args(self.data, self.minio, "/tmp/noble.img", "local-lvm", "local:snippets/1.yaml", "owner")
        self.assertEqual(args[:3], ["qm", "create", str(self.minio["id"])])
        for disk in self.minio["data_disks"]:
            self.assertEqual(args[args.index("--"+disk["slot"])+1], f"local-lvm:20,serial={disk['serial']}")
        self.assertEqual(provision.size_gib("local:vm-disk,size=4096M"), 4)
        self.assertEqual(provision.size_gib("local:vm-disk,size=20G"), 20)
        self.assertNotIn("destroy", args)


if __name__ == "__main__":
    unittest.main()

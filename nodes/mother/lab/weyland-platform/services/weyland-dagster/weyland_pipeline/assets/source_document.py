import base64
import os
import paramiko
from dagster import asset, RetryPolicy


@asset(
    retry_policy=RetryPolicy(max_retries=2, delay=30),
    description="Read weyland.md from rogueone over SSH.",
)
def source_document() -> dict:
    host = os.environ["WEYLAND_SSH_HOST"]
    user = os.environ["WEYLAND_SSH_USER"]
    key_path = os.environ["WEYLAND_SSH_KEY_PATH"]
    file_path = os.environ["WEYLAND_SSH_FILE_PATH"]
    # rogueone's ed25519 HOST public key (base64 blob) — pinned to prevent MITM.
    host_key_b64 = os.environ["WEYLAND_SSH_HOST_KEY"]

    key = paramiko.Ed25519Key.from_private_key_file(key_path)
    client = paramiko.SSHClient()
    # Pin the expected host key and reject anything else — no blind AutoAddPolicy.
    expected_host_key = paramiko.Ed25519Key(data=base64.b64decode(host_key_b64))
    client.get_host_keys().add(host, "ssh-ed25519", expected_host_key)
    client.set_missing_host_key_policy(paramiko.RejectPolicy())

    try:
        client.connect(hostname=host, username=user, pkey=key)
        with client.open_sftp() as sftp:
            with sftp.open(file_path, "r") as f:
                content = f.read().decode("utf-8")
    finally:
        client.close()

    return {
        "content": content,
        "source_path": file_path,
        "source_name": os.path.basename(file_path).replace(".md", ""),
    }

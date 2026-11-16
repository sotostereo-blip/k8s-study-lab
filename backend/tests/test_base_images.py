from pathlib import Path

from app.labs import base_images

LABS = Path(__file__).resolve().parents[2] / "labs"


def test_argocd_toolbox_needs_the_kubernetes_toolbox_first():
    ((image, env, service),) = base_images(LABS, "argocd")
    assert (image, service) == ("k8s-study-lab/toolbox:3", "toolbox")
    assert "k8s-study-lab/toolbox:3" in (LABS / "envs" / env / "compose.yaml").read_text()
    assert [b[0] for b in base_images(LABS, "kubeadm")] == ["k8s-study-lab/toolbox:3"]


def test_environments_built_from_public_images_need_nothing():
    for env in ("single-node", "linux", "gitea", "docker"):
        assert base_images(LABS, env) == []


def test_no_lab_bind_mounts_files_from_the_repo():
    # the backend can run in Docker and use the host engine: host paths would not match
    for f in (LABS / "envs").glob("*/compose.yaml"):
        assert "- ./" not in f.read_text() and "- ../" not in f.read_text(), f


def test_ready_made_images_are_downloaded_and_missing_ones_built_here():
    from app.labs import LabManager

    calls = []

    def runner(cmd, stdin, timeout):
        calls.append(cmd)
        if cmd[:2] == ["docker", "pull"]:   # only the toolbox is published
            return (0, "") if cmd[-1].endswith("/toolbox-gitea:1") else (1, "not found")
        if cmd[:3] == ["docker", "image", "inspect"]:
            return (0, "") if cmd[-1] == "k8s-study-lab/gitea-runner:1" else (1, "")
        return 0, ""

    m = LabManager(LABS, runner=runner)
    m.registry = "ghcr.io/me/k8s-study-lab"
    assert m.pull_prebuilt("gitea", 0) == ["gitea"]     # runner is already here, gitea is not
    assert ["docker", "tag", "ghcr.io/me/k8s-study-lab/toolbox-gitea:1", "k8s-study-lab/toolbox-gitea:1"] in calls

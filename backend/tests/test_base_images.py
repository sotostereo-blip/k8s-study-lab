from pathlib import Path

from app.labs import base_images

LABS = Path(__file__).resolve().parents[2] / "labs"


def test_argocd_toolbox_needs_the_kubernetes_toolbox_first():
    assert base_images(LABS, "argocd") == [("k8s-study-lab/toolbox:3", "secure-node", "toolbox")]


def test_environments_built_from_public_images_need_nothing():
    for env in ("single-node", "linux", "gitea", "docker"):
        assert base_images(LABS, env) == []


def test_no_lab_bind_mounts_files_from_the_repo():
    # the backend can run in Docker and use the host engine: host paths would not match
    for f in (LABS / "envs").glob("*/compose.yaml"):
        assert "- ./" not in f.read_text() and "- ../" not in f.read_text(), f

import pytest

from backend.services.candidate_profile_loader import (
    CandidateProfileLoadError,
    CandidateProfileLoader,
)


def test_loader_reads_profile_and_projects(tmp_path) -> None:
    (tmp_path / "profile.md").write_text(
        "# Profile\n\nPython and FastAPI",
        encoding="utf-8",
    )
    (tmp_path / "projects.md").write_text(
        "# Projects\n\nAI Internship Hunter",
        encoding="utf-8",
    )
    loader = CandidateProfileLoader(data_dir=tmp_path)

    assert loader.load_profile() == "# Profile\n\nPython and FastAPI"
    assert loader.load_projects() == "# Projects\n\nAI Internship Hunter"


def test_loader_raises_error_when_candidate_file_is_missing(tmp_path) -> None:
    loader = CandidateProfileLoader(data_dir=tmp_path)

    with pytest.raises(CandidateProfileLoadError) as exc_info:
        loader.load_profile()

    message = str(exc_info.value)
    assert "profile.md" in message
    assert "profile.example.md" in message

from pathlib import Path
from typing import Optional


class CandidateProfileLoadError(RuntimeError):
    """Raised when candidate profile data cannot be loaded."""


class CandidateProfileLoader:
    def __init__(self, data_dir: Optional[Path] = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self._data_dir = data_dir or project_root / "data"

    def load_profile(self) -> str:
        return self._read_markdown("profile.md")

    def load_projects(self) -> str:
        return self._read_markdown("projects.md")

    def _read_markdown(self, filename: str) -> str:
        path = self._data_dir / filename
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            example_path = path.with_name(f"{path.stem}.example{path.suffix}")
            raise CandidateProfileLoadError(
                f"Unable to read private candidate data file: {path}. "
                f"Create it from the anonymized template at {example_path} "
                "and replace the example content with your own information."
            ) from exc

        if not content:
            raise CandidateProfileLoadError(
                f"Candidate data file is empty: {path}"
            )

        return content

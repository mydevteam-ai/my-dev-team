from functools import lru_cache
from pathlib import Path
import yaml
from devteam import settings

@lru_cache()
def load_skills_catalog() -> list[dict]:
    """Loads a lightweight catalog of available skills."""
    catalog = []
    base_path = settings.skills_dir

    if not base_path.exists() or not base_path.is_dir():
        print(f"Warning: Skills directory '{base_path}' not found.")
        return catalog

    for skill_folder in base_path.iterdir():
        if skill_folder.is_dir():
            skill_file = skill_folder / 'SKILL.md'
            if skill_file.exists():
                try:
                    content = skill_file.read_text(encoding='utf-8')
                    if content.startswith('---'):
                        end_marker = content.find('---', 3)
                        if end_marker != -1:
                            yaml_text = content[3:end_marker].strip()
                            metadata = yaml.safe_load(yaml_text)
                            if metadata and isinstance(metadata, dict):
                                catalog.append({
                                    'name': metadata.get('name', skill_folder.name),
                                    'description': metadata.get('description', 'No description provided.')
                                })
                except Exception as e: # pylint: disable=broad-exception-caught
                    print(f"Error parsing {skill_file}: {e}")

    return catalog


@lru_cache(maxsize=8)
def load_skill(skill_name: str) -> str:
    """Reads the full markdown content of a requested skill."""
    safe_skill_name = Path(skill_name).name
    skill_path = Path(settings.skills_dir) / safe_skill_name / 'SKILL.md'

    if not skill_path.exists():
        error_msg = f"System Error: The knowledge module '{skill_name}' does not exist. Please check the exact spelling in your <skills> list and try again, or proceed with your general knowledge."
        print(error_msg)
        return error_msg

    try:
        content = skill_path.read_text(encoding='utf-8')
        if content.startswith('---'):
            end_marker = content.find('---', 3)
            if end_marker != -1:
                content = content[end_marker + 3:].strip()
        return content
    except Exception: # pylint: disable=broad-exception-caught
        error_msg = f"System Error: Failed to read module '{skill_name}' due to a file error. Proceed using your base knowledge."
        return error_msg

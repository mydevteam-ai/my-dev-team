from devteam.state import ProjectState
from .base_manager import BaseManager
from .planning_manager import PlanningManager

class ProjectManager(PlanningManager, BaseManager):
    """Orchestrates the standard development workflow: planning -> development -> integration."""

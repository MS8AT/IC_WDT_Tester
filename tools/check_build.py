"""Fail a build when its temporary owner dependencies drift."""
from pathlib import Path
import runpy

Import('env')
root = Path(env.subst('$PROJECT_DIR'))
runpy.run_path(str(root / 'tools/project.py'))['checked_dependencies'](root)

import sys
import os
import bpy

repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_dir not in sys.path:
    sys.path.insert(0, repo_dir)

import air_cursor
air_cursor.register()
air_cursor.start_operator()
print("[Air Cursor] Extension registered and operator started on port 9880.")

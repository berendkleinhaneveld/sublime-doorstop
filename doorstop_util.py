import json
from pathlib import Path
import subprocess
import yaml

import sublime

from .doorstop_plugin_api import Setting


class DoorstopReference:
    def __init__(self, region, path=None, file=None, keyword=None, point=None):
        self.region = region
        self.path = path
        self.file = file
        self.keyword = keyword
        self.point = point
        self.row = None
        self.column = None

    def is_valid(self):
        if not self.path:
            return False
        if self.keyword and not self.point:
            return False
        return True


def _is_doorstop_configured(view=None, window=None):
    global settings
    if settings.get(Setting().INTERPRETER) is None:
        return False
    if _doorstop_root(view=view, window=window) is None:
        return False
    return True


def _doorstop_root(view: sublime.View = None, window: sublime.Window = None) -> str:
    global settings
    root = settings.get(Setting().ROOT)
    if root:
        return root
    if view:
        if view.file_name():
            path = Path(view.file_name())
            # best_match = folder with .git as subfolder
            # and a folder that is in close proximity to current opened file?
            folders = view.window().folders()
            rel_paths = [path.relative_to(Path(folder)) for folder in folders]
            shortest_rel_path = None
            result = None
            for rel_path, path in zip(rel_paths, folders):
                if not shortest_rel_path or len(str(rel_path)) < len(
                    str(shortest_rel_path)
                ):
                    shortest_rel_path = rel_path
                    result = path

            return result
    if window:
        if window.folders():
            return window.folders()[0]


def _reference(view: sublime.View):
    # Check the selection
    keyword = None
    selection = view.sel()
    if len(selection) == 1:
        # Only take the first line of the selection, if the
        # selection is multiline
        selected_text = view.substr(selection[0]).split("\n")[0]
        if len(selected_text) > 0:
            keyword = selected_text

    # Create paths
    project_dir = _doorstop_root(view=view)
    current_file = view.window().extract_variables().get("file")
    if not current_file:
        return None

    relative = Path(current_file).relative_to(project_dir)
    result = {
        "path": str(relative),
        "type": "file",
    }
    if keyword:
        result["keyword"] = keyword
    return result


def _run_doorstop_command(args):
    global settings
    interpreter = settings.get(Setting().INTERPRETER)
    # TODO: maybe I could use the 'find_resources' method here from sublime
    script = Path(__file__).parent / "doorstop_cli" / "doorstop_cli.py"
    assert script.is_file()

    try:
        result = subprocess.check_output([interpreter, str(script)] + args)
    except subprocess.CalledProcessError as e:
        print("error: {}".format(e))
        return None
    return result


def _doorstop(item, cmd, *args):
    if isinstance(item, str):
        root = item
    else:
        try:
            root = _doorstop_root(view=item.view)
        except Exception:
            root = _doorstop_root(window=item.window)

    json_result = _run_doorstop_command(["--root", root] + [cmd] + list(args))
    if not json_result:
        return None
    parsed_results = json.loads(json_result.decode("utf-8"))
    return parsed_results


def _parse_reference_region(view, region):
    text = view.substr(region)
    try:
        content = yaml.load(text, Loader=yaml.SafeLoader)
        return content[0]
    except Exception:
        print("Could not parse region: {}".format(text))
    return None


def _region_to_reference(view, region):
    parsed = _parse_reference_region(view, region)
    path = parsed.get("path")
    keyword = parsed.get("keyword")

    reference = DoorstopReference(region, path=path, keyword=keyword)

    if not path:
        return reference

    root = Path(_doorstop_root(view=view))
    file = root / path
    if not file.is_file():
        return reference

    reference.file = str(file)

    with open(str(file), mode="r", encoding="utf-8") as fh:
        point = 0
        row = 1
        line = fh.readline()
        while line:
            if keyword in line:
                reference.point = point
                reference.row = row
                reference.column = line.index(keyword) + 1
                break
            point += len(line)
            row += 1
            line = fh.readline()

    return reference

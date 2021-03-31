from pathlib import Path

import sublime
import sublime_plugin


DOORSTOP_KEY = "doorstop"


def plugin_loaded():
    pass


def plugin_unloaded():
    # TODO: really unload all the commands
    # TODO: cleanup all regions
    pass


class DoorstopDebugCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        import pdb
        import sys

        pdb.Pdb(stdout=sys.__stdout__).set_trace()


class DoorstopCopyReferenceCommand(sublime_plugin.TextCommand):
    """
    Creates content for the paste buffer to be able to paste the
    reference in a doorstop item.

    Example output of self.view.window().extract_variables:
    {
        'file': '/Users/beer/Library/Application Support/Sublime Text 3/Packages/doorstop/doorstop.py',
        'file_base_name': 'doorstop',
        'packages': '/Users/beer/Library/Application Support/Sublime Text 3/Packages',
        'file_extension': 'py',
        'file_name': 'doorstop.py',
        'platform': 'OSX',
        'folder': '/Users/beer/Library/Application Support/Sublime Text 3/Packages/doorstop',
        'file_path': '/Users/beer/Library/Application Support/Sublime Text 3/Packages/doorstop'
    }
    """

    def run(self, edit):
        # Check the selection
        keyword = None
        selection = self.view.sel()
        if len(selection) == 1:
            # Only take the first line of the selection, if the
            # selection is multiline
            keyword = self.view.substr(selection[0]).split("\n")[0]

        # Create paths
        # FIXME: window can have multiple folders open...
        # Maybe try to find the best 'relative' folder for the current_file?
        project_dir = Path(self.view.window().folders()[0])
        current_file = Path(self.view.window().extract_variables()["file"])
        relative = current_file.relative_to(project_dir)

        # Create lines for the clipboard
        lines = ["- path: '{}'".format(str(relative)), "  type: file"]
        if keyword:
            lines.append("  keyword: '{}'".format(keyword))

        sublime.set_clipboard("\n".join(lines))

    def is_enabled(self, *args):
        # FIXME: disable when the filename for this view is None
        return len(self.view.sel()) <= 1


class DoorstopCreateReferenceCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        pass

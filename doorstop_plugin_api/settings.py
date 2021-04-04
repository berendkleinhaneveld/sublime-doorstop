import sublime


class Setting:
    def __init__(self):
        self.INTERPRETER = "python_interpreter"
        self.ROOT = "doorstop_root"

    def __iter__(self):
        for x in dir(self):
            if not x.startswith("_"):
                yield x


FILENAME = "Doorstop.sublime-settings"


class Settings:
    """
    Handles all the settings. A callback method is added for each setting, it
    gets called by ST if that setting is changed in the settings file.
    TODO: sanity checks?
    """

    def __init__(self):
        self.settings = sublime.load_settings(FILENAME)

        for setting in Setting():
            self.settings.add_on_change(setting, lambda: self.setting_changed(setting))

    def get(self, setting):
        return self.settings.get(setting, None)

    def set(self, key, value):
        self.settings.set(key, value)

    def save(self):
        sublime.save_settings(FILENAME)

    def setting_changed(self, key):
        print("Doorstop setting changed: {}".format(key))

    def remove_callbacks(self):
        for setting in Setting():
            self.settings.clear_on_change(setting)

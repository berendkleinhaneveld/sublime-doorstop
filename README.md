# Doorstop - Sublime Text plugin

## Settings

Please specify the following settings in your Sublime project:

```JavaScript
{
   "settings": {
        // Put the full path to a python executable here, preferably
        // from virtualenv that has doorstop installed
        "python_interpreter": "/absolute/path/to/bin/python",

        // Put the full path to the doorstop root folder here
        "doorstop_root": "/absolute/path/to/root/of/doorstop"
    }
}
```
Note that you could create a virtual environment with doorstop installed
just for use with this plugin. That way, `python_interpreter` can be
specified once in the user settings and doesn't have to be added to
projects.

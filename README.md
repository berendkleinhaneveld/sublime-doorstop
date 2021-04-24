# Doorstop - Sublime Text plugin

<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>

Managing doorstop items, references and links can be quite a hassle. This plugin aims to make it easier to manage and navigate doorstop items by highlighting references and links, and providing commands and links to quickly navigate those doorstop references and links.

![Example of highlighted references](/assets/example.png "Example of highlighted references")

## Features

* Navigate to any item through header search
* Highlight (and lint) references and referenced locations
* Highlight and navigate to linked items (also child items)
* Add doorstop items to documents
* Add references to doorstop items
* Add links to doorstop items

## Settings

Please specify the following settings in your Sublime project:

```JavaScript
{
    "settings": {
        // Put the full path to a python executable here, preferably
        // from a virtualenv that has doorstop installed
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

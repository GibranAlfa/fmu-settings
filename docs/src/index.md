# FMU Settings documentation

**FMU Settings** is a tool that simplifies the handling of FMU model metadata and references to master data (required for making FMU results usable in other applications and contexts).

FMU Settings lets you manage static configuration through a graphical user interface (GUI) instead of editing files manually. In FMU Settings GUI, you can:
- Set up FMU project metadata
- Add master data references in FMU models, including 
    - referencing stratigraphic units in e.g. RMS to the stratigraphic column in SMDA
    - *mapping of wells between different FMU components and to the official definitions (SMDA) (future feature, currently not implemented)*
- keeping track of version history for your FMU project settings


### If you are new to FMU Settings
1. Read the [Overview](overview.md) page to learn what FMU Settings is and how it is used.
2. Follow instructions on the [Getting started](getting_started.md) page to get started with FMU Settings for your FMU model(s).
3. Use the [GUI user guide](gui_user_guide.md) to configure and add metadata to your FMU model(s).
4. See also [Terminal commands](terminal_commands.md) for the most common terminal commands relevant for FMU Settings.

### Feedback
If you find bugs, need help or have questions or if you have suggestions for new features, use:
- <a href="https://equinor.enterprise.slack.com/archives/C09MFKN4NC9" target="_blank" rel="noopener noreferrer">#fmu-settings slack channel</a>
- <a href="https://fmu.equinor.com" target="_blank" rel="noopener noreferrer">FMU portal</a>


```{toctree}
:maxdepth: 2
:hidden:

overview.md
getting_started.md
gui_user_guide.md
terminal_commands.md
changelog.md
faq.md

```

# DSW Plugin Service Template

Template repository to create DSW plugins with Python service for backend logic.

## Plugin

### Get Started

1. Fill in the [project metadata](plugin/src/metadata.ts).
1. Define [settings](plugin/src/data/settings-data.ts) and [user settings](plugin/src/data/user-settings-data.ts) data using [zod](https://zod.dev).
    - If you don't want to have any settings, you can delete these files and use `PluginBuilder.createWithNoSettings` instead.
    - If you want just one, you can delete the other and create a null codec instead using `makeNullCodec()`.
1. Start implementing your plugin by defining the components in the [components](plugin/src/components) folder and adding them to the PluginBuilder in [plugin.ts](plugin/src/plugin.ts). See [@ds-wizard/plugin-sdk](https://github.com/ds-wizard/dsw-plugin-sdk) for more details.

### Useful Commands

- `npm run build` = creates a production build of the plugin
- `npm run dev` = watch for file changes and run the dev server (you can change the port in package.json)
- `npm run typecheck` = check for type errors
- `npm run lint` = run linter
- `npm run format` = format the code (however, it is more convenient to set up formatter directly in VS Code, see below)

#### Formatter in VS Code

Create `.vscode/settings.json` for easier code editing:

```json
{
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "esbenp.prettier-vscode"
}
```

## Service

### Get Started

Make sure you have [`uv`](https://github.com/astral-sh/uv) installed before you start developing the service:

1. Update the name of your service (Python package) and related metadata in [pyproject.toml](service/pyproject.toml).
2. Accordingly, change the name of top-level module in [service/src](service/src) folder (rename `plugin_service` folder).
3. Implement your service logic in the [app.py](service/src/plugin_service/app.py) and create additional modules as needed.

### Useful Commands

There is a `Makefile` in the [service](service) folder with useful commands:

- `make install` = install the dependencies in a virtual environment using `uv`
- `make dev` = run the development server (hot-reloads on file changes)
- `make typecheck` = run type checker
- `make lint` = run linter
- `make format` = format the code
- `make requirements` = update `requirements.txt` file

### Development Recommendations

It is recommended to use integrated `uv`, `ruff`, and `ty` in your IDE (e.g., PyCharm or VS Code) for better development experience.

## Readme and License

Update the rest of the readme and delete the template instructions. Update the license in [LICENSE](LICENSE) and [package.json](package.json).

---

# Plugin Name

_Plugin description._

## How to Install

See the [Plugins](https://guide.ds-wizard.org/en/latest/more/self-hosted-dsw/configuration/plugins.html) page in the DSW Guide for instructions on how to install the plugin.

## Changelog

### 0.1.0

Initial version...

## License

This project is licensed under the MIT License - see the
[LICENSE](LICENSE) file for more details.

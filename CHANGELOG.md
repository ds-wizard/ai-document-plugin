# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-09-13

- Added Common templates and option to edit templates (#135)
- Added export to Word (#146)
- Added exporting templates (#151)
- Allowed users to see previously generated DMPs (#142)
- Showed templates based on tenant (#130)
- Separated LLM clients based on tenant (#128)
- Improved security when one tenant is compromised (#131)
- Updated permissions handling for DSW version 0.4.33 (#144)
- Updated prompts so the output matches the template language (#138)
- Replaced server-wide queue and thread pool executor with asyncio (#123, #124)
- Started using dependency injection for configuration (#127)
- Removed unused config values, LLM info is set only in plugin config (#96)
- Updated logging (#150)
- Updated dependencies (#160)

## [0.2.2] - 2026-06-16

- Fixed handling of FileReply

## [0.2.1] - 2026-06-15

- Fixed database DI

## [0.2.0] - 2026-06-15

- Fixed limit maximum parallel executions (#103)
- Fixed tab URL
- Set to run DB migrations on startup
- Updated dependencies

## [0.1.0] - 2026-06-08

- Initial release of the AI Document plugin

[unreleased]: https://github.com/ds-wizard/ai-document-plugin/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ds-wizard/ai-document-plugin/releases/tag/v0.1.0

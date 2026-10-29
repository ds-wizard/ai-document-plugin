# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-10-29

- Added explicit output language selection for document generation (#156)
- Added an optional cover page with DMP and project metadata, configurable in the template and visible in its preview (#180)
- Added version and timestamp information to the pipeline run tab (#191)
- Moved LLM settings (model, API key, API URL, parallel calls) from the DSW plugin settings to the service database and encrypted stored API keys (#186)
- Improved template management UI with modal forms, template actions in the preview header, and simplified scrolling (#195)
- Improved LLM error messages and retry handling, including authentication errors and output token limits (#185)
- Replaced the deprecated max_tokens parameter with max_completion_tokens (#183)
- Replaced AI-generated section IDs with deterministic IDs (#194)
- Fixed language lookup (#172)
- Fixed component updates when switching templates and avoided unnecessary re-rendering (#174)
- Fixed conflicting Alembic migration heads and added a regression check (#198)
- Reworked result storage and collected per-step statistics with trace IDs (#157)
- Used UUID types instead of strings where applicable (#158)
- Added a wrapper for Haystack pipelines (#193)
- Updated the DSW plugin SDK (#189)
- Updated Python and plugin dependencies (#163, #187, #199)

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

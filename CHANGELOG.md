# [1.3.0](https://github.com/frankie336/entities/compare/v1.2.0...v1.3.0) (2025-04-19)


### Features

* Add Redis Server to yml ([828458a](https://github.com/frankie336/entities/commit/828458a7c514a77b1003109915094444dc18f119))
* Add Redis Server to yml ([3cae319](https://github.com/frankie336/entities/commit/3cae319ee2c8108b78180ee5be10d8b647da1713))
* Add Redis Server to yml2 ([a79138c](https://github.com/frankie336/entities/commit/a79138c3d906322cd952d1f56bcd76d8a63f9f0f))

# [1.2.0](https://github.com/frankie336/entities/compare/v1.1.0...v1.2.0) (2025-04-19)


### Features

* Add Redis Server to yml ([1aa1c3b](https://github.com/frankie336/entities/commit/1aa1c3b2f426d86165afd81e68c7faad1a7dcadf))

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

# [1.1.0](https://github.com/frankie336/entities/compare/v1.0.0...v1.1.0) (2025-04-16)

# Changelog - Notable Changes in Dev Version

## Refactoring and Code Quality Improvements

- **F-String Cleanup:**  
  Replaced all f‑strings without any placeholders (F541) with regular string concatenation or proper formatting. This eliminates the flake8 F541 errors.

- **Line Formatting:**  
  Split multiple statements on one line (E701 errors) into individual lines for clarity and compliance with PEP 8.

- **Unused Imports Removed:**  
  Removed or commented out unused imports (e.g., `getpass`, `dotenv.load_dotenv`, and unused members from `os.path`) to resolve F401 errors.

- **Improved Error Messaging:**  
  Enhanced error messages in database connection logic and file I/O operations (such as during credential file writing and .env updates) to be more informative and provide actionable troubleshooting tips.

- **Logging Standardization:**  
  Streamlined logging messages across bootstrap and user-creation scripts to ensure consistency and easier debugging during the bootstrap process.

- **Code Comment Cleanup:**  
  Removed excessive inline comments and redundant annotations to improve overall readability and maintainability of the scripts.

- **Semantic-Release Alignment:**  
  Adjusted version-update commands and file paths (ensuring they correctly reference existing files) to resolve issues with our semantic-release pipeline.

These changes not only resolve the current linting and formatting issues but also enhance the robustness and clarity of our bootstrap and orchestration scripts, ultimately leading to a smoother developer experience.

### Bug Fixes

*.releaserc.json ([c2910f6](https://github.com/frankie336/entities/commit/c2910f6c8cd99393815b15ba7cb2804ac9889f52))
* .releaserc.json[#1](https://github.com/frankie336/entities/issues/1) ([cec1a03](https://github.com/frankie336/entities/commit/cec1a034d62ae71fd6286ec36479143475d0024b))
* syntax issues. ([f21b3a3](https://github.com/frankie336/entities/commit/f21b3a375df72c1af27a3446251de3990bd5d4c7))
* syntax issues[#1](https://github.com/frankie336/entities/issues/1). ([0fa19f0](https://github.com/frankie336/entities/commit/0fa19f05d87d9f7287df485fcb303f83808064e9))


### Features

* unique secrets generate_docker_compose.py ([6ec3efe](https://github.com/frankie336/entities/commit/6ec3efe0599326c2a851d22a020dfe788a963b56))

# 1.0.0 (2025-04-15)


### Bug Fixes

* lint fixes. ([67305f5](https://github.com/frankie336/entities/commit/67305f5b9fd01fece73f40145d90a163c1a95a71))

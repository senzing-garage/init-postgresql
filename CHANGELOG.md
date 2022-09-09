# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
[markdownlint](https://dlaa.me/markdownlint/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.4] - 2022-09-09

### Changed in 1.0.4

- Internal cleanup:
  - From `apt` to `apt-get`
  - Remove unnecessary environment variables
  - Remove unused messages

## [1.0.3] - 2022-08-25

### Changed in 1.0.3

- In `Dockerfile`, bump from `senzing/senzingapi-runtime:3.1.1` to `senzing/senzingapi-runtime:3.2.0`

## [1.0.2] - 2022-08-22

### Changed in 1.0.2

- Fixed behavior of SENZING_ENGINE_CONFIGURATION_JSON.SQL.BACKEND = SQL

## [1.0.1] - 2022-08-22

### Changed in 1.0.1

- Refactored database connection

## [1.0.0] - 2022-08-18

### Added to 1.0.0

- Initial functionality for "mandatory" subcommand
  - Create schema
  - Insert initial Senzing configuration

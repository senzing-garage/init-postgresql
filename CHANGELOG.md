# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
[markdownlint](https://dlaa.me/markdownlint/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.14] - 2024-03-18

### Changed in 1.1.14

- In `Dockerfile`, updated FROM instruction to `senzing/senzingapi-runtime:3.9.0`

## [1.1.13] - 2023-11-14

### Changed in 1.1.13

- In `Dockerfile`, updated FROM instruction to `senzing/senzingapi-runtime:3.8.0`
- In `requirements.txt`, updated:
  - psycopg2-binary==2.9.9

## [1.1.12] - 2023-09-30

### Changed in 1.1.12

- In `Dockerfile`, updated FROM instruction to `senzing/senzingapi-runtime:3.7.1`
- In `requirements.txt`, updated:
  - psycopg2-binary==2.9.8

## [1.1.11] - 2023-06-29

### Changed in 1.1.11

- In `Dockerfile`, updated FROM instruction to `senzing/senzingapi-runtime:3.6.0`

## [1.1.10] - 2023-06-15

### Changed in 1.1.10

- In `Dockerfile`, updated FROM instruction to `senzing/senzingapi-runtime:3.5.3`

## [1.1.9] - 2023-05-09

### Changed in 1.1.9

- In `Dockerfile`, updated FROM instruction to `senzing/senzingapi-runtime:3.5.2`

## [1.1.8] - 2023-04-03

### Changed in 1.1.8

- In `Dockerfile`, updated FROM instruction to `senzing/senzingapi-runtime:3.5.0`
- In `requirements.txt`, updated:
  - psycopg2-binary==2.9.6

## [1.1.7] - 2023-03-01

### Changed in 1.1.7

- Updated Usage statement and documentation

## [1.1.6] - 2023-01-13

### Changed in 1.1.6

- In `Dockerfile`, fix vulnerability exposed by `software-properties-common`

## [1.1.5] - 2023-01-12

### Changed in 1.1.5

- In `Dockerfile`, updated FROM instruction to `senzing/senzingapi-tools:3.4.0`

## [1.1.4] - 2022-10-27

### Changed in 1.1.4

- In `Dockerfile`, updated FROM instruction to `senzing/senzingapi-tools:3.3.2`

## [1.1.3] - 2022-10-11

### Changed in 1.1.3

- In `Dockerfile`, updated FROM instruction to `senzing/senzingapi-tools:3.3.1`
- In `requirements.txt`, updated:
  - psycopg2-binary==2.9.4

## [1.1.2] - 2022-09-28

### Changed in 1.1.2

- In `Dockerfile`, updated FROM instruction to `senzing/senzingapi-tools:3.3.0`
- In `requirements.txt`, updated:
  - setuptools==65.4.0

## [1.1.1] - 2022-09-16

### Changed in 1.1.1

- Fix bug when no database schema

### Added in 1.1.1

- Support for `SENZING_CONFIGURATION_MODIFICATIONS`

## [1.1.0] - 2022-09-15

### Added in 1.1.0

- Support for database schema

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

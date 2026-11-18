# srl_converter - SR Linux Configuration Converter and Diff Tool
Modified version of [`srlconv`](https://github.com/srl-labs/srlconv).

Convert Nokia SR Linux configuration between software versions and compare representations before and after.
(only support forward release conversions)

- Convert your current configuration between versions and storing the new config in json, cli and cli-flat formats.
- Computing the diff between the current and new configuration in json, cli and cli-flat formats.

## Prerequisites

- `curl` to download and execute the installation script.
- [`containerlab`](https://containerlab.dev/) to deploy the SR Linux containers.

## Installation

Install with a single command:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
sh -s -- https://github.com/srl-labs/srlconv/archive/refs/heads/main.zip
```

## Usage

To convert your current configuration between versions, use the `convert` subcommand and provide the current and target versions and the path to the configuration file used as startup config on the current node.  
The command will create a temporary workspace directory and deploy the lab, run configuration conversion, and write artifacts under the workspace `output/` directory.

```bash
srlconv convert \
  --current-version 25.10.1 \
  --current-config my-current.cfg \
  --target-version 25.10.2
  --output my-folder
```

> The current configuration can be provided in json, cli, or cli-flat formats as supported by SR Linux for `startup-config`.

The tool will create a workspace directory (under `/tmp` if not specified) and deploy the lab, run configuration conversion, and write artifacts under the workspace's `output/` directory, e.g. `./my-folder/output`.
Then a diff will be executed against each configuration outputs, and written under the workspace's `diff_files/` directory, e.g. `./my-folder/diff_files`.

At the end of the command execution, the tool will print a table with distinct paths for the current and target configuration in json, cli and cli-flat formats. Additionally, it will print a prompt to open the DeepDiff comparisons for the JSON, CLI, and CLI-flat configurations.

| Option                     | Required | Default                  | Description                                                                            |
| -------------------------- | -------- | ------------------------ | -------------------------------------------------------------------------------------- |
| `--current-version`        | yes      | —                        | Source SR Linux version (e.g. `25.10.1`).                                |
| `--current-config`         | yes      | —                        | Path to the configuration file used as startup config on **srl-current** (must exist). |
| `--current-type`           | no       | `ixr-d2l`                | SR Linux **type** for the current node.                                                |
| `--target-version`         | yes      | —                        | Target SR Linux version. (e.g. `26.3.1`)                                                               |
| `--target-type`            | no       | same as `--current-type` | SR Linux **type** for the target node.                                                 |
| `--output`                 | no       | `/tmp`                   | Workspace folder                                                                       |

If you have a hardware node, extract its running config and provide it as the `--current-config` argument.

## Configuration Diffs

At the end of the command execution, a set of DeepDiff comparisons for the JSON, CLI, and CLI-flat configurations is generated.
This diff should help identify the changes for your existing configuration when migrating to a new major release.

Three different formats:

- JSON
- CLI
- CLI-flat

> Start with the JSON diff, as it is the most detailed, and check the CLI and CLI-flat if needed.

For example, here is a JSON diff between some sample config between versions 25.10.1 and 26.3.1:

```json
{
  "dictionary_item_added": [
    "root['srl_nokia-system:system']['srl_nokia-dns:dns-instance']"
  ],
  "dictionary_item_removed": [
    "root['srl_nokia-system:system']['srl_nokia-dns:dns']"
  ],
  "values_changed": {
    "root['srl_nokia-system:system']['srl_nokia-tls:tls']": {
      "new_value": {
        "profile": [
          {
            "name": "clab-profile",
            "key": 
"$aes1$something",
            "certificate": "-----BEGIN CERTIFICATE-----...",
            "authenticate-client": false
          }
        ]
      },
      "old_value": {
        "server-profile": [
          {
            "name": "clab-profile",
            "key": 
"$aes1$something",
            "certificate": "-----BEGIN CERTIFICATE-----...",
            "authenticate-client": false
          }
        ]
      }
    }
  }
}
```

Look at the `dictionary_item_added`, `dictionary_item_removed` and `values_changed` keys to identify the changes.

Based on the diff above, we can see that `root['srl_nokia-system:system']['srl_nokia-tls:tls']` now has a new value `profile` that was previously a `server-profile`. This is a renaming of the container from `server-profile` to `profile`.

Based on the `dictionary_item_added` and `dictionary_item_removed` keys, we can see that the `root['srl_nokia-system:system']['srl_nokia-dns:dns']` container was removed and a new one called `root['srl_nokia-system:system']['srl_nokia-dns:dns-instance']` was added. This is a change from the single instance `dns` container to a new `dns-instance` list.

When looking at the CLI-Flat diff, we spot the same, however ordering of the items may confuse the diff tool.


## Examples

Minimal conversion:

```bash
srlconv convert \
  --current-version 25.10.1 \
  --current-config ./my-router.cfg.json \
  --target-version 25.10.2
  --output my-folder
```

Different hardware type on the target :

```bash
srlconv convert \
  --current-version v25.10.1 \
  --current-config ./config.json \
  --current-type ixr-d2l \
  --target-version 25.10.2 \
  --target-type ixr-d3l
  --output my-folder
```

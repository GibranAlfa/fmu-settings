# Data models

This page describes the main data models used by FMU Settings.

These models are used for content stored in `.fmu/config.json` and `.fmu/mappings.json`.

In normal use, you update this data through FMU Settings rather than editing the files manually. This reference is useful if you want to understand the schemas behind the application.

## Project config

The project configuration contains:

- general project metadata
- access settings
- masterdata
- model information
- RMS-related information

```{eval-rst}
.. autopydantic_model:: fmu.settings.models.project_config.ProjectConfig
   :members:
   :undoc-members:
   :model-show-json: False
```

## External schemas used in project config

The `masterdata`, `model`, and `access` fields in `ProjectConfig` use schemas provided by FMU datamodels.

```{eval-rst}
.. autopydantic_model:: fmu.datamodels.common.masterdata.Masterdata
   :members:
   :undoc-members:
   :model-show-json: False
```

```{eval-rst}
.. autopydantic_model:: fmu.datamodels.fmu_results.fields.Model
   :members:
   :undoc-members:
   :model-show-json: False
```

```{eval-rst}
.. autopydantic_model:: fmu.datamodels.common.access.Access
   :members:
   :undoc-members:
   :model-show-json: False
```

## Related enums

Some of the schemas above use enums from FMU datamodels. One important example is the access classification level used in `Access`.

```{eval-rst}
.. autoclass:: fmu.datamodels.common.enums.Classification
   :members:
```

## RMS-related models

```{eval-rst}
.. autopydantic_model:: fmu.settings.models.project_config.RmsProject
   :members:
   :undoc-members:
   :model-show-json: False
```

```{eval-rst}
.. autopydantic_model:: fmu.settings.models.project_config.RmsCoordinateSystem
   :members:
   :undoc-members:
   :model-show-json: False
```

```{eval-rst}
.. autopydantic_model:: fmu.settings.models.project_config.RmsStratigraphicZone
   :members:
   :undoc-members:
   :model-show-json: False
```

```{eval-rst}
.. autopydantic_model:: fmu.settings.models.project_config.RmsHorizon
   :members:
   :undoc-members:
   :model-show-json: False
```

```{eval-rst}
.. autopydantic_model:: fmu.settings.models.project_config.RmsWell
   :members:
   :undoc-members:
   :model-show-json: False
```

## Mappings

The mappings file stores saved links between project-specific identifiers and official references.

For stratigraphy, `mappings.json` is essentially a collection of `StratigraphyIdentifierMapping` entries stored inside `StratigraphyMappings`.

```{eval-rst}
.. autopydantic_model:: fmu.settings.models.mappings.Mappings
   :members:
   :undoc-members:
   :model-show-json: False
```

The stratigraphy mappings in `Mappings` use the `StratigraphyMappings` schema from FMU datamodels.

```{eval-rst}
.. autopydantic_model:: fmu.datamodels.context.mappings.StratigraphyMappings
   :members:
   :undoc-members:
   :model-show-json: False
```

## Mapping entry schemas

These are the schemas behind the individual mapping entries stored in `mappings.json`.

```{eval-rst}
.. autopydantic_model:: fmu.datamodels.context.mappings.BaseMapping
   :members:
   :undoc-members:
   :exclude-members: validate_systems_differ
   :model-show-json: False
```

```{eval-rst}
.. autopydantic_model:: fmu.datamodels.context.mappings.IdentifierMapping
   :members:
   :undoc-members:
   :exclude-members: validate_ids_not_empty, validate_equivalent_relation
   :model-show-json: False
```

```{eval-rst}
.. autopydantic_model:: fmu.datamodels.context.mappings.StratigraphyIdentifierMapping
   :members:
   :undoc-members:
   :model-show-json: False
```

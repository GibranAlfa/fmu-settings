from typing import Any, Final

MASTERDATA: Final[dict[str, Any]] = {
    "smda": {
        "country": [
            {
                "identifier": "Norway",
                "uuid": "ad214d85-8a1d-19da-e053-c918a4889309",
            }
        ],
        "discovery": [
            {
                "short_identifier": "DROGON",
                "uuid": "ad214d85-8a1d-19da-e053-c918a4889309",
            }
        ],
        "field": [
            {
                "identifier": "DROGON",
                "uuid": "00000000-0000-0000-0000-000000000000",
            }
        ],
        "coordinate_system": {
            "identifier": "ST_WGS84_UTM37N_P32637",
            "uuid": "ad214d85-dac7-19da-e053-c918a4889309",
        },
        "stratigraphic_column": {
            "identifier": "DROGON_HAS_NO_STRATCOLUMN",
            "uuid": "00000000-0000-0000-0000-000000000000",
        },
    }
}

MODEL: Final[dict[str, Any]] = {
    "name": "Drogon",
    "revision": "26.0.0",
    "description": None,
}


ACCESS: Final[dict[str, Any]] = {
    "asset": {"name": "Drogon"},
    "classification": "internal",
}

RMS_ZONES: Final[list[dict[str, Any]]] = [
    {
        "name": "Above",
        "top_horizon_name": "MSL",
        "base_horizon_name": "TopVolantis",
        "stratigraphic_column_name": ["Column", "Column_1"],
    },
    {
        "name": "Valysar",
        "top_horizon_name": "TopVolantis",
        "base_horizon_name": "TopTherys",
        "stratigraphic_column_name": ["Column"],
    },
    {
        "name": "Therys",
        "top_horizon_name": "TopTherys",
        "base_horizon_name": "TopVolon",
        "stratigraphic_column_name": ["Column"],
    },
    {
        "name": "Volon",
        "top_horizon_name": "TopVolon",
        "base_horizon_name": "BaseVolantis",
        "stratigraphic_column_name": ["Column"],
    },
    {
        "name": "Below",
        "top_horizon_name": "BaseVolantis",
        "base_horizon_name": "BaseVelmodel",
        "stratigraphic_column_name": ["Column", "Column_1"],
    },
]

RMS_HORIZONS: Final[list[dict[str, Any]]] = [
    {"name": "MSL", "type": "interpreted"},
    {"name": "Seabase", "type": "interpreted"},
    {"name": "TopVolantis", "type": "interpreted"},
    {"name": "TopTherys", "type": "interpreted"},
    {"name": "TopVolon", "type": "interpreted"},
    {"name": "BaseVolantis", "type": "interpreted"},
    {"name": "BaseVelmodel", "type": "interpreted"},
]

RMS_WELLS: Final[list[dict[str, str | bool]]] = [
    {"name": "55_33-1", "planned": False},
    {"name": "55_33-2", "planned": False},
    {"name": "55_33-3", "planned": False},
    {"name": "55_33-A-1", "planned": False},
    {"name": "55_33-A-2", "planned": False},
    {"name": "55_33-A-3", "planned": False},
    {"name": "55_33-A-4", "planned": False},
    {"name": "55_33-A-5", "planned": False},
    {"name": "55_33-A-6", "planned": False},
    {"name": "OP5_Y1", "planned": False},
    {"name": "OP5_Y2", "planned": False},
    {"name": "OP6", "planned": False},
    {"name": "MLW_OP5_Y1", "planned": False},
    {"name": "RFT_55_33-A-2", "planned": False},
    {"name": "RFT_55_33-A-3", "planned": False},
    {"name": "RFT_55_33-A-4", "planned": False},
    {"name": "RFT_55_33-A-5", "planned": False},
    {"name": "RFT_55_33-A-6", "planned": False},
]

# Yes, this is the actual value in Drogon.
RMS_COORDINATE_SYSTEM: Final[dict[str, str]] = {"name": "westeros"}

PROJECT_CONFIG_DICT: Final[dict[str, Any]] = {
    "masterdata": MASTERDATA,
    "model": MODEL,
    "access": ACCESS,
    "rms": {
        "path": "rms/model/drogon.rms15.0.1.0",
        "version": "15.0.1.0",
        "coordinate_system": RMS_COORDINATE_SYSTEM,
        "zones": RMS_ZONES,
        "horizons": RMS_HORIZONS,
        "wells": RMS_WELLS,
    },
}

GLOBAL_CONFIG_STRATIGRAPHY: Final[dict[str, Any]] = {
    "MSL": {
        "stratigraphic": False,
        "name": "MSL",
    },
    "Seabase": {
        "stratigraphic": False,
        "name": "Seabase",
    },
    "TopVolantis": {
        "stratigraphic": True,
        "name": "VOLANTIS GP. Top",
        "alias": ["TopVOLANTIS", "TOP_VOLANTIS"],
    },
    "TopTherys": {"stratigraphic": True, "name": "Therys Fm. Top"},
    "TopVolon": {"stratigraphic": True, "name": "Volon Fm. Top"},
    "BaseVolon": {"stratigraphic": True, "name": "Volon Fm. Base"},
    "BaseVolantis": {"stratigraphic": True, "name": "VOLANTIS GP. Base"},
    "BaseVelmodel": {"stratigraphic": False, "name": "BaseVelmodel"},
    "Above": {"stratigraphic": False, "name": "Above"},
    "Valysar": {"stratigraphic": True, "name": "Valysar Fm."},
    "Therys": {"stratigraphic": True, "name": "Therys Fm."},
    "Volon": {"stratigraphic": True, "name": "Volon Fm."},
    "Below": {"stratigraphic": False, "name": "Below"},
}

STRATIGRAPHY_MAPPINGS: Final[list[dict[str, Any]]] = [
    {
        "source_system": "rms",
        "target_system": "rms",
        "relation_type": "primary",
        "source_id": "TopVolantis",
        "target_id": "TopVolantis",
        "target_uuid": None,
    },
    {
        "source_system": "rms",
        "target_system": "rms",
        "relation_type": "alias",
        "source_id": "TopVOLANTIS",
        "target_id": "TopVolantis",
        "target_uuid": None,
    },
    {
        "source_system": "rms",
        "target_system": "rms",
        "relation_type": "alias",
        "source_id": "TOP_VOLANTIS",
        "target_id": "TopVolantis",
        "target_uuid": None,
    },
    {
        "source_system": "rms",
        "target_system": "smda",
        "relation_type": "primary",
        "source_id": "TopVolantis",
        "target_id": "VOLANTIS GP. Top",
        "target_uuid": "1629c229-0a2b-4f0a-94f7-dc01b171cb1c",
    },
    {
        "source_system": "rms",
        "target_system": "rms",
        "relation_type": "primary",
        "source_id": "TopTherys",
        "target_id": "TopTherys",
        "target_uuid": None,
    },
    {
        "source_system": "rms",
        "target_system": "smda",
        "relation_type": "primary",
        "source_id": "TopTherys",
        "target_id": "Therys Fm. Top",
        "target_uuid": "0240dc8e-659a-4925-b569-6f1570ba6770",
    },
    {
        "source_system": "rms",
        "target_system": "rms",
        "relation_type": "primary",
        "source_id": "TopVolon",
        "target_id": "TopVolon",
        "target_uuid": None,
    },
    {
        "source_system": "rms",
        "target_system": "smda",
        "relation_type": "primary",
        "source_id": "TopVolon",
        "target_id": "Volon Fm. Top",
        "target_uuid": "0240dc8e-659a-4925-b569-6f1570ba6770",
    },
    {
        "source_system": "rms",
        "target_system": "rms",
        "relation_type": "primary",
        "source_id": "BaseVolon",
        "target_id": "BaseVolon",
        "target_uuid": None,
    },
    {
        "source_system": "rms",
        "target_system": "smda",
        "relation_type": "primary",
        "source_id": "BaseVolon",
        "target_id": "Volon Fm. Base",
        "target_uuid": "433bd00d-9cf8-4eec-9a35-8bac0821f07c",
    },
    {
        "source_system": "rms",
        "target_system": "rms",
        "relation_type": "primary",
        "source_id": "BaseVolantis",
        "target_id": "BaseVolantis",
        "target_uuid": None,
    },
    {
        "source_system": "rms",
        "target_system": "smda",
        "relation_type": "primary",
        "source_id": "BaseVolantis",
        "target_id": "VOLANTIS GP. Base",
        "target_uuid": "3c36a234-91e3-4bc5-8642-f32b910c5c6c",
    },
    {
        "source_system": "rms",
        "target_system": "rms",
        "relation_type": "primary",
        "source_id": "Valysar",
        "target_id": "Valysar",
        "target_uuid": None,
    },
    {
        "source_system": "rms",
        "target_system": "smda",
        "relation_type": "primary",
        "source_id": "Valysar",
        "target_id": "Valysar Fm.",
        "target_uuid": "a9cdeb70-af4f-4e86-a209-4eb124ac096a",
    },
    {
        "source_system": "rms",
        "target_system": "rms",
        "relation_type": "primary",
        "source_id": "Therys",
        "target_id": "Therys",
        "target_uuid": None,
    },
    {
        "source_system": "rms",
        "target_system": "smda",
        "relation_type": "primary",
        "source_id": "Therys",
        "target_id": "Therys Fm.",
        "target_uuid": "a21c5998-9506-44d8-b29d-208c817e3a0b",
    },
    {
        "source_system": "rms",
        "target_system": "rms",
        "relation_type": "primary",
        "source_id": "Volon",
        "target_id": "Volon",
        "target_uuid": None,
    },
    {
        "source_system": "rms",
        "target_system": "smda",
        "relation_type": "primary",
        "source_id": "Volon",
        "target_id": "Volon Fm.",
        "target_uuid": "a6d740be-ef58-4569-9fad-2daf17aa214c",
    },
]

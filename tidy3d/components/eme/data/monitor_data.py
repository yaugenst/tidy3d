"""EME monitor data"""

from typing import Union

from pydantic import Field

from ...base_sim.data.monitor_data import AbstractMonitorData
from ...data.monitor_data import ElectromagneticFieldData, ModeSolverData, PermittivityData
from ..monitor import EMECoefficientMonitor, EMEFieldMonitor, EMEModeSolverMonitor
from .dataset import EMECoefficientDataset, EMEFieldDataset, EMEModeSolverDataset


class EMEModeSolverData(ElectromagneticFieldData, EMEModeSolverDataset):
    """Data associated with an EME mode solver monitor."""

    monitor: EMEModeSolverMonitor = Field(
        title="EME Mode Solver Monitor",
        description="EME mode solver monitor associated with this data.",
    )


class EMEFieldData(ElectromagneticFieldData, EMEFieldDataset):
    """Data associated with an EME field monitor."""

    monitor: EMEFieldMonitor = Field(
        title="EME Field Monitor",
        description="EME field monitor associated with this data.",
    )


class EMECoefficientData(AbstractMonitorData, EMECoefficientDataset):
    """Data associated with an EME coefficient monitor."""

    monitor: EMECoefficientMonitor = Field(
        title="EME Coefficient Monitor",
        description="EME coefficient monitor associated with this data.",
    )


EMEMonitorDataType = Union[
    EMEModeSolverData, EMEFieldData, EMECoefficientData, ModeSolverData, PermittivityData
]

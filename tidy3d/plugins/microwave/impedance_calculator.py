"""Class for computing characteristic impedance of transmission lines."""

from __future__ import annotations

from typing import Optional, Union

import numpy as np
import pydantic.v1 as pd

from ...components.base import Tidy3dBaseModel
from ...components.data.data_array import FreqDataArray, FreqModeDataArray, TimeDataArray
from ...components.data.monitor_data import FieldTimeData
from ...constants import OHM
from ...exceptions import ValidationError
from .auto_path_integrals import CompositeCurrentIntegral
from .custom_path_integrals import CustomCurrentIntegral2D, CustomVoltageIntegral2D
from .path_integrals import (
    AxisAlignedPathIntegral,
    CurrentIntegralAxisAligned,
    IntegralResultTypes,
    MonitorDataTypes,
    VoltageIntegralAxisAligned,
)

VoltageIntegralTypes = Union[VoltageIntegralAxisAligned, CustomVoltageIntegral2D]
CurrentIntegralTypes = Union[
    CurrentIntegralAxisAligned, CustomCurrentIntegral2D, CompositeCurrentIntegral
]


class ImpedanceCalculator(Tidy3dBaseModel):
    """Tool for computing the characteristic impedance of a transmission line."""

    voltage_integral: Optional[VoltageIntegralTypes] = pd.Field(
        None,
        title="Voltage Integral",
        description="Definition of path integral for computing voltage.",
    )

    current_integral: Optional[CurrentIntegralTypes] = pd.Field(
        None,
        title="Current Integral",
        description="Definition of contour integral for computing current.",
    )

    def compute_impedance(self, em_field: MonitorDataTypes) -> IntegralResultTypes:
        """Compute impedance for the supplied ``em_field`` using ``voltage_integral`` and
        ``current_integral``. If only a single integral has been defined, impedance is
        computed using the total flux in ``em_field``.

        Parameters
        ----------
        em_field : :class:`.MonitorDataTypes`
            The electromagnetic field data that will be used for computing the characteristic
            impedance.

        Returns
        -------
        :class:`.IntegralResultTypes`
            Result of impedance computation over remaining dimensions (frequency, time, mode indices).
        """
        AxisAlignedPathIntegral._check_monitor_data_supported(em_field=em_field)

        # If both voltage and current integrals have been defined then impedance is computed directly
        if self.voltage_integral is not None:
            voltage = self.voltage_integral.compute_voltage(em_field)
        if self.current_integral is not None:
            current = self.current_integral.compute_current(em_field)

        # If only one of the integrals has been provided, then the computation falls back to using
        # total power (flux) with Ohm's law to compute the missing quantity. The input field should
        # cover an area large enough to render the flux computation accurate. If the input field is
        # a time signal, then it is real and flux corresponds to the instantaneous power. Otherwise
        # the input field is in frequency domain, where flux indicates the time-averaged power
        # 0.5*Re(V*conj(I)).
        if self.voltage_integral is None:
            flux = em_field.flux
            if isinstance(em_field, FieldTimeData):
                impedance = flux.abs / current**2
            else:
                impedance = 2 * flux.abs / (current * np.conj(current))
                # voltage = 2 * flux.abs / np.conj(current)
        elif self.current_integral is None:
            flux = em_field.flux
            if isinstance(em_field, FieldTimeData):
                impedance = voltage**2 / flux.abs
                # current = flux.abs / voltage
            else:
                impedance = (voltage * np.conj(voltage)) / (2 * flux.abs)
                # current = np.conj(2 * flux.abs / voltage)
        else:
            impedance = voltage / current
        impedance = ImpedanceCalculator._set_data_array_attributes(impedance)
        return impedance

    @pd.validator("current_integral", always=True)
    def check_voltage_or_current(cls, val, values):
        """Raise validation error if both ``voltage_integral`` and ``current_integral``
        are not provided."""
        if not values.get("voltage_integral") and not val:
            raise ValidationError(
                "At least one of 'voltage_integral' or 'current_integral' must be provided."
            )
        return val

    @staticmethod
    def _set_data_array_attributes(data_array: IntegralResultTypes) -> IntegralResultTypes:
        """Helper to set additional metadata for ``IntegralResultTypes``."""
        # Determine type based on coords present
        if "mode_index" in data_array.coords:
            data_array = FreqModeDataArray(data_array)
        elif "f" in data_array.coords:
            data_array = FreqDataArray(data_array)
        else:
            data_array = TimeDataArray(data_array)
        data_array.name = "Z0"
        return data_array.assign_attrs(units=OHM, long_name="characteristic impedance")

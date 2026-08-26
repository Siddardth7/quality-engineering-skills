"""
quality_core.sqe

Supplier Quality Engineering (SQE) suite. Exports the receipt-lot, delivery-record, and SCAR
request schemas, their row/dataset models, the caller-constructed Supplier/SupplierPeriod
identity models, and the CSV ingest loaders (Issue #115), plus the supplier PPM/DPMO defect-rate
engine (Issue #116), the OTIF & delivery-performance calculator (Issue #117), and the composed
vendor scorecard engine (Issue #118). The escalation ladder and SCAR generator land in E5-E6.
"""

from __future__ import annotations

from quality_core.sqe.otif import (
    OTIFConfig,
    OTIFResult,
    calculate_otif,
)
from quality_core.sqe.ppm import (
    PPMConfig,
    PPMResult,
    calculate_supplier_ppm,
)
from quality_core.sqe.schema import (
    SQE_DELIVERY_SCHEMA,
    SQE_RECEIPT_SCHEMA,
    SQE_SCAR_SCHEMA,
    DeliveryRecord,
    DeliveryRecordDataset,
    IngestError,
    ReceiptLot,
    ReceiptLotDataset,
    SCARRequest,
    SCARRequestDataset,
    Supplier,
    SupplierPeriod,
    load_sqe_delivery_csv,
    load_sqe_receipt_csv,
    load_sqe_scar_csv,
    validate_sqe_delivery,
    validate_sqe_receipt,
    validate_sqe_scar,
)
from quality_core.sqe.scorecard import (
    LinearScoringCurve,
    ScorecardConfig,
    ScorecardDimensionResult,
    ScorecardResult,
    calculate_vendor_scorecard,
)

__all__ = [
    "DeliveryRecord",
    "DeliveryRecordDataset",
    "IngestError",
    "LinearScoringCurve",
    "OTIFConfig",
    "OTIFResult",
    "PPMConfig",
    "PPMResult",
    "ReceiptLot",
    "ReceiptLotDataset",
    "SCARRequest",
    "SCARRequestDataset",
    "SQE_DELIVERY_SCHEMA",
    "SQE_RECEIPT_SCHEMA",
    "SQE_SCAR_SCHEMA",
    "Supplier",
    "SupplierPeriod",
    "ScorecardConfig",
    "ScorecardDimensionResult",
    "ScorecardResult",
    "calculate_otif",
    "calculate_supplier_ppm",
    "calculate_vendor_scorecard",
    "load_sqe_delivery_csv",
    "load_sqe_receipt_csv",
    "load_sqe_scar_csv",
    "validate_sqe_delivery",
    "validate_sqe_receipt",
    "validate_sqe_scar",
]

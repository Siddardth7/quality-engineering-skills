"""
quality_core.sqe

Supplier Quality Engineering (SQE) suite. Exports the receipt-lot, delivery-record, and SCAR
request schemas, their row/dataset models, the caller-constructed Supplier/SupplierPeriod
identity models, and the CSV ingest loaders (Issue #115), plus the supplier PPM/DPMO defect-rate
engine (Issue #116), the OTIF & delivery-performance calculator (Issue #117), the composed
vendor scorecard engine (Issue #118), and the SCAR generator with cross-engine evidence linkage
(Issue #120). The escalation ladder lands in E5.
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
from quality_core.sqe.scar import (
    SCARConfig,
    SCARLinkageResult,
    SCARResult,
    SCARSection,
    generate_scar,
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
    "SCARConfig",
    "SCARLinkageResult",
    "SCARRequest",
    "SCARRequestDataset",
    "SCARResult",
    "SCARSection",
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
    "generate_scar",
    "load_sqe_delivery_csv",
    "load_sqe_receipt_csv",
    "load_sqe_scar_csv",
    "validate_sqe_delivery",
    "validate_sqe_receipt",
    "validate_sqe_scar",
]

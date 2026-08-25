"""
quality_core.sqe

Supplier Quality Engineering (SQE) suite. Exports the receipt-lot, delivery-record, and SCAR
request schemas, their row/dataset models, the caller-constructed Supplier/SupplierPeriod
identity models, and the CSV ingest loaders (Issue #115), plus the supplier PPM/DPMO defect-rate
engine (Issue #116) and the OTIF & delivery-performance calculator (Issue #117). Vendor scorecard,
escalation ladder, and SCAR generator land in E4-E6.
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

__all__ = [
    "DeliveryRecord",
    "DeliveryRecordDataset",
    "IngestError",
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
    "calculate_otif",
    "calculate_supplier_ppm",
    "load_sqe_delivery_csv",
    "load_sqe_receipt_csv",
    "load_sqe_scar_csv",
    "validate_sqe_delivery",
    "validate_sqe_receipt",
    "validate_sqe_scar",
]

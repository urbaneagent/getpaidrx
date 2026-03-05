"""
Pharmacy Inventory Shrinkage Detector
========================================
Detects and alerts on inventory shrinkage through discrepancy analysis
between expected and actual inventory levels, identifies loss patterns,
and provides investigation workflows for controlled and high-value drugs.

Features:
- Real-time inventory discrepancy detection
- Controlled substance tracking with DEA schedule awareness
- Perpetual inventory reconciliation engine
- Shrinkage pattern analysis (time-of-day, shift, employee)
- Loss categorization (theft, damage, expiration, dispensing error)
- Investigation workflow with evidence collection
- ABC classification for prioritized monitoring
- Regulatory compliance alerts (DEA, state board)

Author: GetPaidRx Engineering
Version: 1.0.0
"""

import json
import math
import hashlib
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class DEASchedule(Enum):
    SCHEDULE_II = "CII"     # Highest abuse potential (oxycodone, fentanyl)
    SCHEDULE_III = "CIII"   # Moderate (codeine combinations)
    SCHEDULE_IV = "CIV"     # Lower (benzodiazepines)
    SCHEDULE_V = "CV"       # Lowest (cough syrups with codeine)
    NON_CONTROLLED = "NC"   # Not a controlled substance


class ShrinkageType(Enum):
    THEFT = "theft"
    DISPENSING_ERROR = "dispensing_error"
    DAMAGE = "damage"
    EXPIRATION = "expiration"
    VENDOR_SHORT = "vendor_short"
    COUNTING_ERROR = "counting_error"
    DIVERSION = "diversion"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    CRITICAL = "critical"    # Controlled substance, large quantity
    HIGH = "high"            # High-value drug or pattern detected
    MEDIUM = "medium"        # Moderate discrepancy
    LOW = "low"              # Small discrepancy, likely counting error
    INFO = "info"            # Informational


class ABCClass(Enum):
    A = "A"   # Top 20% by value (80% of total value)
    B = "B"   # Next 30% by value (15% of total value)
    C = "C"   # Bottom 50% by value (5% of total value)


@dataclass
class DrugInventoryItem:
    """A single drug in inventory."""
    ndc: str
    drug_name: str
    generic_name: str
    dea_schedule: DEASchedule
    abc_class: ABCClass
    unit_cost: float
    expected_quantity: float      # What the system says we should have
    actual_quantity: float        # Physical count
    reorder_point: int
    par_level: int
    last_count_date: str
    last_receipt_date: str = ""
    last_dispensed_date: str = ""
    lot_number: str = ""
    expiration_date: str = ""
    location: str = "shelf"       # shelf, safe, fridge, vault
    supplier: str = ""


@dataclass
class InventoryTransaction:
    """Record of an inventory transaction."""
    transaction_id: str
    ndc: str
    transaction_type: str         # receipt, dispense, return, adjustment, transfer, waste
    quantity: float
    employee_id: str
    timestamp: str
    reference_id: str = ""        # Rx number, PO number, etc.
    notes: str = ""
    verified_by: str = ""


@dataclass
class ShrinkageAlert:
    """An alert generated for detected shrinkage."""
    alert_id: str
    ndc: str
    drug_name: str
    dea_schedule: DEASchedule
    severity: AlertSeverity
    shrinkage_type: ShrinkageType
    expected_quantity: float
    actual_quantity: float
    discrepancy: float
    value_loss: float
    description: str
    investigation_required: bool
    regulatory_report_required: bool
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    acknowledged: bool = False
    acknowledged_by: str = ""
    investigation_status: str = "pending"
    resolution: str = ""


@dataclass
class InvestigationCase:
    """Investigation case for significant shrinkage events."""
    case_id: str
    alert_ids: List[str]
    drug_name: str
    ndc: str
    total_discrepancy: float
    total_value: float
    status: str = "open"          # open, investigating, resolved, referred
    assigned_to: str = ""
    opened_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    findings: List[str] = field(default_factory=list)
    evidence: List[Dict] = field(default_factory=list)
    resolution_type: str = ""     # found, adjusted, reported, referred_to_dea
    closed_at: Optional[str] = None


class PerpetualInventoryEngine:
    """Maintains and reconciles perpetual inventory records."""

    def __init__(self):
        self.inventory: Dict[str, DrugInventoryItem] = {}
        self.transactions: List[InventoryTransaction] = []
        self._transaction_counter = 0

    def add_item(self, item: DrugInventoryItem):
        self.inventory[item.ndc] = item

    def record_receipt(self, ndc: str, quantity: float, employee_id: str,
                       po_number: str = "", lot: str = "") -> Optional[InventoryTransaction]:
        item = self.inventory.get(ndc)
        if not item:
            return None

        self._transaction_counter += 1
        txn = InventoryTransaction(
            transaction_id=f"TXN-{self._transaction_counter:08d}",
            ndc=ndc,
            transaction_type="receipt",
            quantity=quantity,
            employee_id=employee_id,
            timestamp=datetime.utcnow().isoformat(),
            reference_id=po_number,
            notes=f"Lot: {lot}" if lot else ""
        )

        item.expected_quantity += quantity
        item.last_receipt_date = datetime.utcnow().isoformat()[:10]
        self.transactions.append(txn)
        return txn

    def record_dispense(self, ndc: str, quantity: float, employee_id: str,
                        rx_number: str = "") -> Optional[InventoryTransaction]:
        item = self.inventory.get(ndc)
        if not item:
            return None

        self._transaction_counter += 1
        txn = InventoryTransaction(
            transaction_id=f"TXN-{self._transaction_counter:08d}",
            ndc=ndc,
            transaction_type="dispense",
            quantity=-quantity,
            employee_id=employee_id,
            timestamp=datetime.utcnow().isoformat(),
            reference_id=rx_number
        )

        item.expected_quantity -= quantity
        item.last_dispensed_date = datetime.utcnow().isoformat()[:10]
        self.transactions.append(txn)
        return txn

    def record_physical_count(self, ndc: str, counted_quantity: float,
                               employee_id: str) -> Dict:
        item = self.inventory.get(ndc)
        if not item:
            return {"error": "Item not found"}

        discrepancy = counted_quantity - item.expected_quantity

        result = {
            "ndc": ndc,
            "drug_name": item.drug_name,
            "expected": item.expected_quantity,
            "counted": counted_quantity,
            "discrepancy": discrepancy,
            "value_impact": round(abs(discrepancy) * item.unit_cost, 2),
            "has_discrepancy": abs(discrepancy) > 0.5
        }

        item.actual_quantity = counted_quantity
        item.last_count_date = datetime.utcnow().isoformat()[:10]

        if abs(discrepancy) > 0.5:
            self._transaction_counter += 1
            txn = InventoryTransaction(
                transaction_id=f"TXN-{self._transaction_counter:08d}",
                ndc=ndc,
                transaction_type="adjustment",
                quantity=discrepancy,
                employee_id=employee_id,
                timestamp=datetime.utcnow().isoformat(),
                notes=f"Physical count adjustment: expected {item.expected_quantity}, counted {counted_quantity}"
            )
            self.transactions.append(txn)
            item.expected_quantity = counted_quantity

        return result

    def get_transaction_history(self, ndc: str, days: int = 30) -> List[Dict]:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        return [
            {
                "transaction_id": t.transaction_id,
                "type": t.transaction_type,
                "quantity": t.quantity,
                "employee": t.employee_id,
                "timestamp": t.timestamp,
                "reference": t.reference_id,
                "notes": t.notes
            }
            for t in self.transactions
            if t.ndc == ndc and t.timestamp >= cutoff
        ]


class ShrinkagePatternAnalyzer:
    """Analyzes patterns in inventory shrinkage events."""

    def __init__(self):
        self.shrinkage_events: List[Dict] = []

    def record_event(self, ndc: str, drug_name: str, discrepancy: float,
                     value: float, employee_id: str, shift: str,
                     dea_schedule: DEASchedule):
        self.shrinkage_events.append({
            "ndc": ndc,
            "drug_name": drug_name,
            "discrepancy": discrepancy,
            "value": value,
            "employee_id": employee_id,
            "shift": shift,
            "dea_schedule": dea_schedule.value,
            "timestamp": datetime.utcnow().isoformat(),
            "day_of_week": datetime.utcnow().strftime("%A"),
            "hour": datetime.utcnow().hour
        })

    def analyze_patterns(self, days: int = 90) -> Dict:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        recent = [e for e in self.shrinkage_events if e["timestamp"] >= cutoff]

        if not recent:
            return {"message": "No shrinkage events in period", "days": days}

        # By employee
        by_employee = defaultdict(lambda: {"count": 0, "total_value": 0, "drugs": set()})
        for e in recent:
            emp = by_employee[e["employee_id"]]
            emp["count"] += 1
            emp["total_value"] += e["value"]
            emp["drugs"].add(e["drug_name"])

        # By shift
        by_shift = defaultdict(lambda: {"count": 0, "total_value": 0})
        for e in recent:
            shift = by_shift[e["shift"]]
            shift["count"] += 1
            shift["total_value"] += e["value"]

        # By day of week
        by_day = defaultdict(lambda: {"count": 0, "total_value": 0})
        for e in recent:
            day = by_day[e["day_of_week"]]
            day["count"] += 1
            day["total_value"] += e["value"]

        # By drug
        by_drug = defaultdict(lambda: {"count": 0, "total_value": 0, "total_units": 0})
        for e in recent:
            drug = by_drug[e["drug_name"]]
            drug["count"] += 1
            drug["total_value"] += e["value"]
            drug["total_units"] += abs(e["discrepancy"])

        # Controlled substance focus
        controlled = [e for e in recent if e["dea_schedule"] != "NC"]

        # Anomaly detection
        anomalies = []
        for emp_id, stats in by_employee.items():
            if stats["count"] >= 5:
                anomalies.append({
                    "type": "frequent_employee",
                    "employee_id": emp_id,
                    "count": stats["count"],
                    "value": round(stats["total_value"], 2),
                    "description": f"Employee {emp_id} involved in {stats['count']} shrinkage events"
                })

        for drug, stats in by_drug.items():
            if stats["count"] >= 3:
                anomalies.append({
                    "type": "frequently_short_drug",
                    "drug_name": drug,
                    "count": stats["count"],
                    "total_units": stats["total_units"],
                    "description": f"{drug} has {stats['count']} shrinkage events in {days} days"
                })

        return {
            "period_days": days,
            "total_events": len(recent),
            "total_value_lost": round(sum(e["value"] for e in recent), 2),
            "controlled_substance_events": len(controlled),
            "by_employee": {
                emp: {"count": s["count"], "value": round(s["total_value"], 2), "drugs": list(s["drugs"])}
                for emp, s in sorted(by_employee.items(), key=lambda x: x[1]["total_value"], reverse=True)
            },
            "by_shift": {shift: {"count": s["count"], "value": round(s["total_value"], 2)} for shift, s in by_shift.items()},
            "by_day_of_week": {day: {"count": s["count"], "value": round(s["total_value"], 2)} for day, s in by_day.items()},
            "top_shrinkage_drugs": [
                {"drug": drug, "count": s["count"], "value": round(s["total_value"], 2), "units": s["total_units"]}
                for drug, s in sorted(by_drug.items(), key=lambda x: x[1]["total_value"], reverse=True)[:10]
            ],
            "anomalies": anomalies,
            "analyzed_at": datetime.utcnow().isoformat()
        }


class ShrinkageAlertEngine:
    """Generates and manages shrinkage alerts."""

    def __init__(self):
        self.alerts: List[ShrinkageAlert] = []
        self._alert_counter = 0

    # Thresholds by DEA schedule
    THRESHOLDS = {
        DEASchedule.SCHEDULE_II: {"units": 1, "value": 10},
        DEASchedule.SCHEDULE_III: {"units": 2, "value": 25},
        DEASchedule.SCHEDULE_IV: {"units": 3, "value": 50},
        DEASchedule.SCHEDULE_V: {"units": 5, "value": 75},
        DEASchedule.NON_CONTROLLED: {"units": 10, "value": 100},
    }

    def evaluate_discrepancy(self, item: DrugInventoryItem,
                              counted: float) -> Optional[ShrinkageAlert]:
        discrepancy = item.expected_quantity - counted
        if discrepancy <= 0:
            return None  # Overage, not shrinkage

        threshold = self.THRESHOLDS.get(item.dea_schedule, {"units": 10, "value": 100})
        value_loss = discrepancy * item.unit_cost

        if discrepancy < threshold["units"] and value_loss < threshold["value"]:
            return None  # Below threshold

        severity = self._determine_severity(item, discrepancy, value_loss)
        shrinkage_type = self._classify_shrinkage(item, discrepancy)

        self._alert_counter += 1
        alert = ShrinkageAlert(
            alert_id=f"SHRINK-{self._alert_counter:06d}",
            ndc=item.ndc,
            drug_name=item.drug_name,
            dea_schedule=item.dea_schedule,
            severity=severity,
            shrinkage_type=shrinkage_type,
            expected_quantity=item.expected_quantity,
            actual_quantity=counted,
            discrepancy=discrepancy,
            value_loss=round(value_loss, 2),
            description=self._build_description(item, discrepancy, value_loss, shrinkage_type),
            investigation_required=(
                severity in (AlertSeverity.CRITICAL, AlertSeverity.HIGH) or
                item.dea_schedule in (DEASchedule.SCHEDULE_II, DEASchedule.SCHEDULE_III)
            ),
            regulatory_report_required=(
                item.dea_schedule == DEASchedule.SCHEDULE_II and discrepancy >= 1
            )
        )

        self.alerts.append(alert)
        return alert

    def _determine_severity(self, item: DrugInventoryItem,
                             discrepancy: float, value_loss: float) -> AlertSeverity:
        if item.dea_schedule == DEASchedule.SCHEDULE_II:
            return AlertSeverity.CRITICAL
        if item.dea_schedule == DEASchedule.SCHEDULE_III and discrepancy >= 5:
            return AlertSeverity.CRITICAL
        if value_loss >= 500:
            return AlertSeverity.CRITICAL
        if value_loss >= 100 or item.dea_schedule in (DEASchedule.SCHEDULE_III, DEASchedule.SCHEDULE_IV):
            return AlertSeverity.HIGH
        if value_loss >= 25:
            return AlertSeverity.MEDIUM
        return AlertSeverity.LOW

    def _classify_shrinkage(self, item: DrugInventoryItem, discrepancy: float) -> ShrinkageType:
        # Heuristic classification
        if item.dea_schedule in (DEASchedule.SCHEDULE_II, DEASchedule.SCHEDULE_III):
            if discrepancy >= 5:
                return ShrinkageType.DIVERSION
            return ShrinkageType.UNKNOWN

        if discrepancy <= 2 and item.unit_cost < 10:
            return ShrinkageType.COUNTING_ERROR

        if item.expiration_date:
            try:
                exp = date.fromisoformat(item.expiration_date)
                if exp <= date.today() + timedelta(days=30):
                    return ShrinkageType.EXPIRATION
            except ValueError:
                pass

        if discrepancy >= 10:
            return ShrinkageType.THEFT

        return ShrinkageType.UNKNOWN

    def _build_description(self, item: DrugInventoryItem, discrepancy: float,
                            value_loss: float, shrinkage_type: ShrinkageType) -> str:
        desc = (
            f"Inventory discrepancy detected for {item.drug_name} ({item.ndc}). "
            f"Expected: {item.expected_quantity}, Counted: {item.actual_quantity}, "
            f"Short: {discrepancy} units (${value_loss:.2f}). "
        )

        if item.dea_schedule != DEASchedule.NON_CONTROLLED:
            desc += f"DEA Schedule: {item.dea_schedule.value}. "

        desc += f"Classification: {shrinkage_type.value}. "

        if shrinkage_type == ShrinkageType.DIVERSION:
            desc += "⚠️ POSSIBLE DIVERSION - IMMEDIATE INVESTIGATION REQUIRED. "
        if item.dea_schedule == DEASchedule.SCHEDULE_II:
            desc += "⚠️ SCHEDULE II - DEA reporting may be required. "

        return desc

    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Dict]:
        alerts = self.alerts
        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return [
            {
                "alert_id": a.alert_id,
                "drug_name": a.drug_name,
                "ndc": a.ndc,
                "severity": a.severity.value,
                "dea_schedule": a.dea_schedule.value,
                "discrepancy": a.discrepancy,
                "value_loss": a.value_loss,
                "shrinkage_type": a.shrinkage_type.value,
                "investigation_required": a.investigation_required,
                "regulatory_report": a.regulatory_report_required,
                "detected_at": a.detected_at,
                "status": a.investigation_status
            }
            for a in sorted(alerts, key=lambda x: list(AlertSeverity).index(x.severity))
        ]


class InventoryShrinkageDetector:
    """
    Main orchestrator for pharmacy inventory shrinkage detection.
    
    Usage:
        detector = InventoryShrinkageDetector()
        detector.add_inventory_item(item)
        detector.record_receipt(ndc, qty, employee)
        detector.record_dispense(ndc, qty, employee, rx)
        
        count_result = detector.physical_count(ndc, counted_qty, employee)
        patterns = detector.analyze_patterns()
    """

    def __init__(self):
        self.perpetual = PerpetualInventoryEngine()
        self.alert_engine = ShrinkageAlertEngine()
        self.pattern_analyzer = ShrinkagePatternAnalyzer()
        self.investigations: Dict[str, InvestigationCase] = {}
        self._case_counter = 0

    def add_inventory_item(self, item: DrugInventoryItem):
        self.perpetual.add_item(item)

    def record_receipt(self, ndc: str, quantity: float, employee_id: str, po: str = ""):
        return self.perpetual.record_receipt(ndc, quantity, employee_id, po)

    def record_dispense(self, ndc: str, quantity: float, employee_id: str, rx: str = ""):
        return self.perpetual.record_dispense(ndc, quantity, employee_id, rx)

    def physical_count(self, ndc: str, counted_quantity: float,
                       employee_id: str, shift: str = "day") -> Dict:
        count_result = self.perpetual.record_physical_count(ndc, counted_quantity, employee_id)

        if count_result.get("has_discrepancy"):
            item = self.perpetual.inventory.get(ndc)
            if item:
                alert = self.alert_engine.evaluate_discrepancy(item, counted_quantity)

                if alert:
                    self.pattern_analyzer.record_event(
                        ndc, item.drug_name, alert.discrepancy,
                        alert.value_loss, employee_id, shift, item.dea_schedule
                    )
                    count_result["alert"] = {
                        "alert_id": alert.alert_id,
                        "severity": alert.severity.value,
                        "investigation_required": alert.investigation_required,
                        "regulatory_report": alert.regulatory_report_required
                    }

                    if alert.investigation_required:
                        case = self._create_investigation(alert, item)
                        count_result["investigation"] = {
                            "case_id": case.case_id,
                            "status": case.status
                        }

        return count_result

    def _create_investigation(self, alert: ShrinkageAlert, item: DrugInventoryItem) -> InvestigationCase:
        self._case_counter += 1
        case = InvestigationCase(
            case_id=f"INV-{self._case_counter:06d}",
            alert_ids=[alert.alert_id],
            drug_name=item.drug_name,
            ndc=item.ndc,
            total_discrepancy=alert.discrepancy,
            total_value=alert.value_loss
        )

        # Add transaction history as evidence
        history = self.perpetual.get_transaction_history(item.ndc, days=30)
        case.evidence.append({
            "type": "transaction_history",
            "data": history,
            "description": f"30-day transaction history for {item.drug_name}"
        })

        self.investigations[case.case_id] = case
        return case

    def analyze_patterns(self, days: int = 90) -> Dict:
        return self.pattern_analyzer.analyze_patterns(days)

    def get_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Dict]:
        return self.alert_engine.get_active_alerts(severity)

    def get_dashboard(self) -> Dict:
        total_items = len(self.perpetual.inventory)
        controlled = sum(1 for i in self.perpetual.inventory.values()
                        if i.dea_schedule != DEASchedule.NON_CONTROLLED)
        
        alerts = self.alert_engine.alerts
        open_investigations = sum(1 for c in self.investigations.values() if c.status == "open")

        total_value_at_risk = sum(a.value_loss for a in alerts if a.investigation_status == "pending")

        return {
            "inventory": {
                "total_items": total_items,
                "controlled_substances": controlled,
                "total_transactions": len(self.perpetual.transactions)
            },
            "alerts": {
                "total": len(alerts),
                "critical": len([a for a in alerts if a.severity == AlertSeverity.CRITICAL]),
                "high": len([a for a in alerts if a.severity == AlertSeverity.HIGH]),
                "pending_investigation": len([a for a in alerts if a.investigation_status == "pending"])
            },
            "investigations": {
                "total": len(self.investigations),
                "open": open_investigations,
                "total_value_at_risk": round(total_value_at_risk, 2)
            },
            "regulatory": {
                "dea_reports_needed": len([a for a in alerts if a.regulatory_report_required and not a.acknowledged])
            },
            "generated_at": datetime.utcnow().isoformat()
        }


# FastAPI Integration
try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/v1/shrinkage", tags=["Inventory Shrinkage"])
    detector = InventoryShrinkageDetector()

    @router.get("/dashboard")
    async def dashboard():
        return detector.get_dashboard()

    @router.get("/alerts")
    async def get_alerts(severity: Optional[str] = None):
        sev = AlertSeverity(severity) if severity else None
        return {"alerts": detector.get_alerts(sev)}

    @router.get("/patterns")
    async def analyze_patterns(days: int = 90):
        return detector.analyze_patterns(days)

except ImportError:
    router = None

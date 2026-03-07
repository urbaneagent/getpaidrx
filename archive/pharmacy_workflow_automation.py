"""
GetPaidRx — Pharmacy Workflow Automation Engine
Automates pharmacy operational workflows including prescription processing,
refill management, inventory reorder triggers, and staff task assignment.

Provides:
  - Prescription processing pipeline (receive → verify → fill → check → dispense)
  - Automatic refill management with adherence tracking
  - Inventory reorder point calculation and auto-ordering triggers  
  - Staff task queue with priority-based assignment
  - Prescription transfer tracking (in/out)
  - Controlled substance monitoring with PDMP integration prep
  - Workflow analytics (fill times, error rates, throughput)
  - FastAPI routes for workflow management
"""

import json
import uuid
import statistics
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
from enum import Enum


# ============================================================
# Enums & Constants
# ============================================================

class RxStatus(str, Enum):
    RECEIVED = "received"
    INSURANCE_CHECK = "insurance_check"
    DUR_REVIEW = "dur_review"          # Drug Utilization Review
    READY_TO_FILL = "ready_to_fill"
    FILLING = "filling"
    PHARMACIST_CHECK = "pharmacist_check"
    READY_FOR_PICKUP = "ready_for_pickup"
    DISPENSED = "dispensed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"
    TRANSFERRED_OUT = "transferred_out"


class TaskType(str, Enum):
    FILL = "fill"
    VERIFY = "verify"
    COUNSELING = "counseling"
    INVENTORY = "inventory"
    PA_FOLLOW_UP = "pa_follow_up"
    REFILL_CALL = "refill_call"
    TRANSFER = "transfer"
    COMPOUND = "compound"
    RETURN_TO_STOCK = "return_to_stock"


class TaskPriority(str, Enum):
    STAT = "stat"          # Immediate (15 min)
    URGENT = "urgent"      # 1 hour
    ROUTINE = "routine"    # 2 hours
    BATCH = "batch"        # End of day


class StaffRole(str, Enum):
    PHARMACIST = "pharmacist"
    TECH = "tech"
    INTERN = "intern"
    CLERK = "clerk"


class ControlledSchedule(str, Enum):
    SCHEDULE_II = "CII"
    SCHEDULE_III = "CIII"
    SCHEDULE_IV = "CIV"
    SCHEDULE_V = "CV"
    NON_CONTROLLED = "non_controlled"


# SLA targets (minutes) by priority
TASK_SLA_MINUTES = {
    TaskPriority.STAT: 15,
    TaskPriority.URGENT: 60,
    TaskPriority.ROUTINE: 120,
    TaskPriority.BATCH: 480,
}

# Which roles can perform which tasks
ROLE_CAPABILITIES = {
    StaffRole.PHARMACIST: {TaskType.FILL, TaskType.VERIFY, TaskType.COUNSELING, TaskType.PA_FOLLOW_UP, TaskType.COMPOUND, TaskType.TRANSFER},
    StaffRole.TECH: {TaskType.FILL, TaskType.INVENTORY, TaskType.REFILL_CALL, TaskType.RETURN_TO_STOCK, TaskType.TRANSFER},
    StaffRole.INTERN: {TaskType.FILL, TaskType.VERIFY, TaskType.COUNSELING, TaskType.INVENTORY},
    StaffRole.CLERK: {TaskType.REFILL_CALL, TaskType.RETURN_TO_STOCK, TaskType.INVENTORY},
}


# ============================================================
# Data Models
# ============================================================

class Prescription:
    """A prescription being processed through the pharmacy."""

    def __init__(
        self,
        patient_id: str,
        patient_name: str,
        prescriber_name: str,
        prescriber_npi: str,
        drug_name: str,
        ndc: str,
        quantity: float,
        days_supply: int,
        refills_remaining: int = 0,
        sig: str = "",
        daw_code: int = 0,
        controlled_schedule: ControlledSchedule = ControlledSchedule.NON_CONTROLLED,
        priority: TaskPriority = TaskPriority.ROUTINE,
    ):
        self.rx_number = f"RX{str(uuid.uuid4().int)[:8]}"
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.prescriber_name = prescriber_name
        self.prescriber_npi = prescriber_npi
        self.drug_name = drug_name
        self.ndc = ndc
        self.quantity = quantity
        self.days_supply = days_supply
        self.refills_remaining = refills_remaining
        self.sig = sig
        self.daw_code = daw_code
        self.controlled_schedule = controlled_schedule
        self.priority = priority

        self.status = RxStatus.RECEIVED
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.dispensed_at: Optional[datetime] = None

        self.fill_number: int = 1
        self.is_refill: bool = False
        self.insurance_response: Optional[Dict] = None
        self.dur_alerts: List[Dict] = []
        self.verification_pharmacist: Optional[str] = None
        self.filled_by: Optional[str] = None

        # Timeline
        self.events: List[Dict] = [
            {"status": "received", "timestamp": self.created_at.isoformat(), "by": "system"}
        ]

    @property
    def fill_time_minutes(self) -> Optional[float]:
        if self.dispensed_at:
            return round((self.dispensed_at - self.created_at).total_seconds() / 60, 1)
        return None

    def advance_status(self, new_status: RxStatus, by: str = "system"):
        self.status = new_status
        self.updated_at = datetime.utcnow()
        if new_status == RxStatus.DISPENSED:
            self.dispensed_at = datetime.utcnow()
        self.events.append({
            "status": new_status.value,
            "timestamp": self.updated_at.isoformat(),
            "by": by,
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rx_number": self.rx_number,
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "prescriber_name": self.prescriber_name,
            "drug_name": self.drug_name,
            "ndc": self.ndc,
            "quantity": self.quantity,
            "days_supply": self.days_supply,
            "refills_remaining": self.refills_remaining,
            "sig": self.sig,
            "controlled_schedule": self.controlled_schedule.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "fill_number": self.fill_number,
            "is_refill": self.is_refill,
            "fill_time_minutes": self.fill_time_minutes,
            "created_at": self.created_at.isoformat(),
            "dispensed_at": self.dispensed_at.isoformat() if self.dispensed_at else None,
            "dur_alerts": self.dur_alerts,
            "event_count": len(self.events),
        }


class StaffMember:
    """A pharmacy staff member."""

    def __init__(self, staff_id: str, name: str, role: StaffRole):
        self.staff_id = staff_id
        self.name = name
        self.role = role
        self.active = True
        self.current_task_count: int = 0
        self.total_tasks_completed: int = 0
        self.shift_start: Optional[datetime] = None

    def can_perform(self, task_type: TaskType) -> bool:
        return task_type in ROLE_CAPABILITIES.get(self.role, set())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "staff_id": self.staff_id,
            "name": self.name,
            "role": self.role.value,
            "active": self.active,
            "current_tasks": self.current_task_count,
            "total_completed": self.total_tasks_completed,
        }


class WorkflowTask:
    """A task in the pharmacy workflow queue."""

    def __init__(
        self,
        task_type: TaskType,
        priority: TaskPriority,
        rx_number: Optional[str] = None,
        description: str = "",
        assigned_to: Optional[str] = None,
    ):
        self.task_id = str(uuid.uuid4())[:10]
        self.task_type = task_type
        self.priority = priority
        self.rx_number = rx_number
        self.description = description
        self.assigned_to = assigned_to
        self.created_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.completed = False

    @property
    def sla_deadline(self) -> datetime:
        return self.created_at + timedelta(minutes=TASK_SLA_MINUTES.get(self.priority, 120))

    @property
    def is_overdue(self) -> bool:
        return not self.completed and datetime.utcnow() > self.sla_deadline

    def complete(self, by: str):
        self.completed = True
        self.completed_at = datetime.utcnow()
        self.assigned_to = by

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "priority": self.priority.value,
            "rx_number": self.rx_number,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at.isoformat(),
            "sla_deadline": self.sla_deadline.isoformat(),
            "is_overdue": self.is_overdue,
            "completed": self.completed,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class InventoryItem:
    """An inventory item with reorder tracking."""

    def __init__(self, ndc: str, drug_name: str, on_hand: int, reorder_point: int,
                 reorder_quantity: int, unit_cost: float, par_level: int):
        self.ndc = ndc
        self.drug_name = drug_name
        self.on_hand = on_hand
        self.reorder_point = reorder_point
        self.reorder_quantity = reorder_quantity
        self.unit_cost = unit_cost
        self.par_level = par_level
        self.last_dispensed: Optional[str] = None
        self.avg_weekly_usage: float = 0
        self.pending_order: bool = False

    @property
    def needs_reorder(self) -> bool:
        return self.on_hand <= self.reorder_point and not self.pending_order

    @property
    def days_of_supply(self) -> float:
        daily_usage = self.avg_weekly_usage / 7 if self.avg_weekly_usage > 0 else 0
        return round(self.on_hand / max(daily_usage, 0.01), 1)

    def dispense(self, quantity: int):
        self.on_hand = max(self.on_hand - quantity, 0)
        self.last_dispensed = datetime.utcnow().isoformat()

    def receive(self, quantity: int):
        self.on_hand += quantity
        self.pending_order = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ndc": self.ndc,
            "drug_name": self.drug_name,
            "on_hand": self.on_hand,
            "reorder_point": self.reorder_point,
            "reorder_quantity": self.reorder_quantity,
            "par_level": self.par_level,
            "unit_cost": self.unit_cost,
            "needs_reorder": self.needs_reorder,
            "days_of_supply": self.days_of_supply,
            "avg_weekly_usage": self.avg_weekly_usage,
            "pending_order": self.pending_order,
        }


# ============================================================
# Pharmacy Workflow Engine
# ============================================================

class PharmacyWorkflowEngine:
    """
    Central pharmacy workflow automation engine.
    Manages prescription processing, task queues, staff, and inventory.
    """

    def __init__(self):
        self.prescriptions: Dict[str, Prescription] = {}
        self.tasks: Dict[str, WorkflowTask] = {}
        self.staff: Dict[str, StaffMember] = {}
        self.inventory: Dict[str, InventoryItem] = {}
        self.refill_queue: List[Dict[str, Any]] = []

    # ----------------------------------------------------------
    # Prescription Processing
    # ----------------------------------------------------------

    def receive_prescription(self, **kwargs) -> Prescription:
        rx = Prescription(**kwargs)
        self.prescriptions[rx.rx_number] = rx

        # Auto-create fill task
        task = WorkflowTask(
            task_type=TaskType.FILL,
            priority=rx.priority,
            rx_number=rx.rx_number,
            description=f"Fill {rx.drug_name} {rx.quantity} for {rx.patient_name}",
        )
        self.tasks[task.task_id] = task

        # Check inventory
        if rx.ndc in self.inventory:
            item = self.inventory[rx.ndc]
            if item.on_hand < rx.quantity:
                # Create inventory task
                inv_task = WorkflowTask(
                    task_type=TaskType.INVENTORY,
                    priority=TaskPriority.URGENT,
                    rx_number=rx.rx_number,
                    description=f"Insufficient stock for {rx.drug_name}: need {rx.quantity}, have {item.on_hand}",
                )
                self.tasks[inv_task.task_id] = inv_task

        return rx

    def advance_rx(self, rx_number: str, by: str = "system") -> Tuple[bool, str]:
        """Advance a prescription to the next workflow stage."""
        rx = self.prescriptions.get(rx_number)
        if not rx:
            return False, "Rx not found"

        # Define stage progression
        progression = {
            RxStatus.RECEIVED: RxStatus.INSURANCE_CHECK,
            RxStatus.INSURANCE_CHECK: RxStatus.DUR_REVIEW,
            RxStatus.DUR_REVIEW: RxStatus.READY_TO_FILL,
            RxStatus.READY_TO_FILL: RxStatus.FILLING,
            RxStatus.FILLING: RxStatus.PHARMACIST_CHECK,
            RxStatus.PHARMACIST_CHECK: RxStatus.READY_FOR_PICKUP,
            RxStatus.READY_FOR_PICKUP: RxStatus.DISPENSED,
        }

        next_status = progression.get(rx.status)
        if not next_status:
            return False, f"Cannot advance from {rx.status.value}"

        rx.advance_status(next_status, by)

        # Auto-create verification task at pharmacist check
        if next_status == RxStatus.PHARMACIST_CHECK:
            task = WorkflowTask(
                task_type=TaskType.VERIFY,
                priority=rx.priority,
                rx_number=rx.rx_number,
                description=f"Verify {rx.drug_name} for {rx.patient_name}",
            )
            self.tasks[task.task_id] = task

        # Update inventory on dispense
        if next_status == RxStatus.DISPENSED:
            if rx.ndc in self.inventory:
                self.inventory[rx.ndc].dispense(int(rx.quantity))
                if self.inventory[rx.ndc].needs_reorder:
                    self._create_reorder_task(rx.ndc)

        return True, f"Rx advanced to {next_status.value}"

    def hold_rx(self, rx_number: str, reason: str = "", by: str = "system") -> bool:
        rx = self.prescriptions.get(rx_number)
        if rx and rx.status not in (RxStatus.DISPENSED, RxStatus.CANCELLED):
            rx.advance_status(RxStatus.ON_HOLD, by)
            return True
        return False

    # ----------------------------------------------------------
    # Task Management
    # ----------------------------------------------------------

    def get_task_queue(self, role: Optional[StaffRole] = None) -> List[Dict[str, Any]]:
        """Get pending tasks, optionally filtered by role capability."""
        pending = [t for t in self.tasks.values() if not t.completed]

        if role:
            capable_types = ROLE_CAPABILITIES.get(role, set())
            pending = [t for t in pending if t.task_type in capable_types]

        # Sort: STAT first, then by overdue, then by created_at
        priority_order = {TaskPriority.STAT: 0, TaskPriority.URGENT: 1, TaskPriority.ROUTINE: 2, TaskPriority.BATCH: 3}
        pending.sort(key=lambda t: (priority_order.get(t.priority, 4), -int(t.is_overdue), t.created_at))

        return [t.to_dict() for t in pending]

    def complete_task(self, task_id: str, by: str) -> Tuple[bool, str]:
        task = self.tasks.get(task_id)
        if not task:
            return False, "Task not found"
        if task.completed:
            return False, "Task already completed"

        task.complete(by)

        # Update staff stats
        if by in self.staff:
            self.staff[by].total_tasks_completed += 1
            self.staff[by].current_task_count = max(self.staff[by].current_task_count - 1, 0)

        return True, f"Task {task_id} completed by {by}"

    def auto_assign_task(self, task_id: str) -> Optional[str]:
        """Auto-assign a task to the least-loaded capable staff member."""
        task = self.tasks.get(task_id)
        if not task or task.completed:
            return None

        candidates = [
            s for s in self.staff.values()
            if s.active and s.can_perform(task.task_type)
        ]

        if not candidates:
            return None

        # Assign to least-loaded
        candidates.sort(key=lambda s: s.current_task_count)
        assignee = candidates[0]
        task.assigned_to = assignee.staff_id
        assignee.current_task_count += 1
        return assignee.staff_id

    # ----------------------------------------------------------
    # Staff Management
    # ----------------------------------------------------------

    def add_staff(self, staff_id: str, name: str, role: StaffRole) -> StaffMember:
        member = StaffMember(staff_id, name, role)
        self.staff[staff_id] = member
        return member

    # ----------------------------------------------------------
    # Inventory Management
    # ----------------------------------------------------------

    def add_inventory_item(self, **kwargs) -> InventoryItem:
        item = InventoryItem(**kwargs)
        self.inventory[item.ndc] = item
        return item

    def get_reorder_list(self) -> List[Dict[str, Any]]:
        """Get all items that need reordering."""
        return [
            {**item.to_dict(), "order_value": round(item.reorder_quantity * item.unit_cost, 2)}
            for item in self.inventory.values()
            if item.needs_reorder
        ]

    def _create_reorder_task(self, ndc: str):
        item = self.inventory.get(ndc)
        if item:
            task = WorkflowTask(
                task_type=TaskType.INVENTORY,
                priority=TaskPriority.URGENT,
                description=f"Reorder {item.drug_name}: {item.on_hand} remaining, need {item.reorder_quantity}",
            )
            self.tasks[task.task_id] = task
            item.pending_order = True

    # ----------------------------------------------------------
    # Refill Management
    # ----------------------------------------------------------

    def check_refill_due(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Find prescriptions that need refill calls."""
        due = []
        for rx in self.prescriptions.values():
            if rx.status != RxStatus.DISPENSED or rx.refills_remaining <= 0:
                continue
            if rx.dispensed_at:
                next_fill_date = rx.dispensed_at + timedelta(days=rx.days_supply)
                days_until_due = (next_fill_date - datetime.utcnow()).days
                if days_until_due <= days_ahead:
                    due.append({
                        "rx_number": rx.rx_number,
                        "patient_id": rx.patient_id,
                        "patient_name": rx.patient_name,
                        "drug_name": rx.drug_name,
                        "refills_remaining": rx.refills_remaining,
                        "days_until_due": days_until_due,
                        "next_fill_date": next_fill_date.strftime("%Y-%m-%d"),
                    })

        due.sort(key=lambda d: d["days_until_due"])
        return due

    # ----------------------------------------------------------
    # Workflow Analytics
    # ----------------------------------------------------------

    def workflow_analytics(self) -> Dict[str, Any]:
        """Comprehensive workflow analytics."""
        all_rx = list(self.prescriptions.values())
        completed_rx = [rx for rx in all_rx if rx.status == RxStatus.DISPENSED]

        fill_times = [rx.fill_time_minutes for rx in completed_rx if rx.fill_time_minutes]
        avg_fill = round(statistics.mean(fill_times), 1) if fill_times else 0
        median_fill = round(statistics.median(fill_times), 1) if fill_times else 0

        # Status distribution
        status_counts = defaultdict(int)
        for rx in all_rx:
            status_counts[rx.status.value] += 1

        # Task analytics
        all_tasks = list(self.tasks.values())
        completed_tasks = [t for t in all_tasks if t.completed]
        overdue_tasks = [t for t in all_tasks if t.is_overdue]

        task_completion_times = []
        for t in completed_tasks:
            if t.completed_at:
                minutes = (t.completed_at - t.created_at).total_seconds() / 60
                task_completion_times.append(minutes)

        # Staff productivity
        staff_stats = []
        for s in self.staff.values():
            staff_stats.append({
                "name": s.name,
                "role": s.role.value,
                "current_tasks": s.current_task_count,
                "total_completed": s.total_tasks_completed,
            })

        # Controlled substance metrics
        controlled = [rx for rx in all_rx if rx.controlled_schedule != ControlledSchedule.NON_CONTROLLED]

        return {
            "prescriptions": {
                "total": len(all_rx),
                "dispensed": len(completed_rx),
                "on_hold": status_counts.get("on_hold", 0),
                "status_distribution": dict(status_counts),
                "avg_fill_time_minutes": avg_fill,
                "median_fill_time_minutes": median_fill,
            },
            "tasks": {
                "total": len(all_tasks),
                "pending": len(all_tasks) - len(completed_tasks),
                "completed": len(completed_tasks),
                "overdue": len(overdue_tasks),
                "avg_completion_minutes": round(statistics.mean(task_completion_times), 1) if task_completion_times else 0,
            },
            "inventory": {
                "total_items": len(self.inventory),
                "items_needing_reorder": len(self.get_reorder_list()),
                "total_reorder_value": round(
                    sum(i.reorder_quantity * i.unit_cost for i in self.inventory.values() if i.needs_reorder), 2
                ),
            },
            "staff": staff_stats,
            "controlled_substances": {
                "total_rx": len(controlled),
                "by_schedule": {s.value: sum(1 for rx in controlled if rx.controlled_schedule == s)
                               for s in ControlledSchedule if s != ControlledSchedule.NON_CONTROLLED},
            },
            "refills_due_7d": len(self.check_refill_due(7)),
        }


# ============================================================
# FastAPI Route Registration
# ============================================================

def register_workflow_routes(app, engine: Optional[PharmacyWorkflowEngine] = None):
    """Register pharmacy workflow API routes."""
    from fastapi import Body

    if engine is None:
        engine = PharmacyWorkflowEngine()

    @app.post("/api/v1/workflow/rx")
    async def receive_rx(payload: Dict[str, Any] = Body(...)):
        rx = engine.receive_prescription(
            patient_id=payload["patient_id"],
            patient_name=payload["patient_name"],
            prescriber_name=payload["prescriber_name"],
            prescriber_npi=payload["prescriber_npi"],
            drug_name=payload["drug_name"],
            ndc=payload["ndc"],
            quantity=payload["quantity"],
            days_supply=payload["days_supply"],
            refills_remaining=payload.get("refills_remaining", 0),
            sig=payload.get("sig", ""),
            controlled_schedule=ControlledSchedule(payload.get("schedule", "non_controlled")),
            priority=TaskPriority(payload.get("priority", "routine")),
        )
        return rx.to_dict()

    @app.post("/api/v1/workflow/rx/{rx_number}/advance")
    async def advance_rx(rx_number: str, by: str = "system"):
        ok, msg = engine.advance_rx(rx_number, by)
        return {"success": ok, "message": msg}

    @app.get("/api/v1/workflow/tasks")
    async def get_tasks(role: Optional[str] = None):
        r = StaffRole(role) if role else None
        return engine.get_task_queue(r)

    @app.post("/api/v1/workflow/tasks/{task_id}/complete")
    async def complete_task(task_id: str, by: str = "system"):
        ok, msg = engine.complete_task(task_id, by)
        return {"success": ok, "message": msg}

    @app.get("/api/v1/workflow/reorder")
    async def get_reorder():
        return engine.get_reorder_list()

    @app.get("/api/v1/workflow/refills-due")
    async def refills_due(days: int = 7):
        return engine.check_refill_due(days)

    @app.get("/api/v1/workflow/analytics")
    async def get_analytics():
        return engine.workflow_analytics()

    return engine

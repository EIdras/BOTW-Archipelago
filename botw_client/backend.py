"""Platform-independent contract for transaction-safe BOTW integrations."""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class DeliveryStatus(str, Enum):
    APPLIED = "applied"
    DEFERRED = "deferred"
    INVENTORY_FULL = "inventory_full"
    ALREADY_APPLIED = "already_applied"
    UNCERTAIN = "uncertain"
    SESSION_MISMATCH = "session_mismatch"
    OUT_OF_ORDER = "out_of_order"


@dataclass(frozen=True)
class DeliveryCommand:
    seed: str
    slot: int
    index: int
    item_name: str
    step: int = 0
    step_count: int = 1
    received_before: int = 0
    # Giving back an item a reloaded save lost: its silent entry, if the step
    # has one (the game's get window is replaced by one AP summary).
    quiet: bool = False

    def __post_init__(self):
        if (self.index < 0 or self.received_before < 0
                or not 0 <= self.step < self.step_count <= 0x100):
            raise ValueError(
                f"position de livraison invalide: {self.index}/{self.step}/"
                f"{self.step_count}")

    @property
    def cursor(self) -> int:
        return (self.index << 8) | self.step

    @property
    def next_cursor(self) -> int:
        if self.step + 1 < self.step_count:
            return (self.index << 8) | (self.step + 1)
        return (self.index + 1) << 8


@dataclass(frozen=True)
class DeliveryCheckpoint:
    """Identity and packed AP item/sub-step committed in the BOTW save.

    ``cursor`` encodes ``(received_index << 8) | step``.
    """

    seed: str
    slot: int
    cursor: int


@dataclass(frozen=True)
class DeliveryResult:
    status: DeliveryStatus
    cursor: int
    detail: str = ""


class TransactionalBackend(Protocol):
    """Contract, not a claim that the legacy Cemu backend implements it.

    APPLIED must mean that both the mutation and the cursor belong to the same
    coherent save state. UNCERTAIN means that a mutation may have happened and
    must never be retried blindly. DEFERRED and INVENTORY_FULL must leave the
    cursor unchanged.
    """
    def deliver(self, command: DeliveryCommand) -> DeliveryResult: ...
    def checkpoint(self) -> DeliveryCheckpoint: ...
    def checked_locations(self) -> set[int]: ...


class BackendContractError(RuntimeError):
    """The native backend returned a state unsafe to reconcile automatically."""


class DeliveryCoordinator:
    """Serialize one delivery without ever retrying an ambiguous mutation.

    This coordinator does not make a sequence of native actions atomic. It
    provides the companion-side safety boundary for the future native writer:
    exact session and cursor checks, strict result validation, and quarantine
    after an exception or UNCERTAIN response.
    """

    def __init__(self, backend: TransactionalBackend):
        self.backend = backend

    @staticmethod
    def _same_session(checkpoint: DeliveryCheckpoint,
                      command: DeliveryCommand) -> bool:
        return (checkpoint.seed, checkpoint.slot) == (command.seed, command.slot)

    @staticmethod
    def _result(status: DeliveryStatus, cursor: int, detail: str = ""):
        return DeliveryResult(status, cursor, detail)

    def _reconcile_unknown(self, command: DeliveryCommand,
                           detail: str) -> DeliveryResult:
        try:
            checkpoint = self.backend.checkpoint()
        except Exception as exc:
            suffix = f"; checkpoint illisible: {exc}"
            return self._result(DeliveryStatus.UNCERTAIN, command.cursor,
                                detail + suffix)
        if not self._same_session(checkpoint, command):
            return self._result(
                DeliveryStatus.UNCERTAIN, checkpoint.cursor,
                detail + "; session changee pendant la livraison")
        if checkpoint.cursor == command.next_cursor:
            return self._result(DeliveryStatus.APPLIED, checkpoint.cursor,
                                detail + "; commit confirme par relecture")
        if checkpoint.cursor == command.cursor:
            return self._result(
                DeliveryStatus.UNCERTAIN, checkpoint.cursor,
                detail + "; curseur inchange, mutation possible")
        raise BackendContractError(
            f"reconciliation #{command.index}/{command.step}: curseur "
            f"{checkpoint.cursor}, attendu {command.cursor} ou "
            f"{command.next_cursor}")

    def deliver(self, command: DeliveryCommand) -> DeliveryResult:
        checkpoint = self.backend.checkpoint()
        if not self._same_session(checkpoint, command):
            return self._result(
                DeliveryStatus.SESSION_MISMATCH, checkpoint.cursor,
                f"sauvegarde {checkpoint.seed}/{checkpoint.slot}, "
                f"commande {command.seed}/{command.slot}")
        if checkpoint.cursor > command.cursor:
            return self._result(DeliveryStatus.ALREADY_APPLIED,
                                checkpoint.cursor)
        if checkpoint.cursor < command.cursor:
            return self._result(
                DeliveryStatus.OUT_OF_ORDER, checkpoint.cursor,
                f"curseur {checkpoint.cursor} attendu avant {command.cursor}")

        try:
            result = self.backend.deliver(command)
        except Exception as exc:
            return self._reconcile_unknown(command, f"backend interrompu: {exc}")

        if result.status in (DeliveryStatus.APPLIED,
                             DeliveryStatus.ALREADY_APPLIED):
            if result.cursor != command.next_cursor:
                raise BackendContractError(
                    f"{result.status.value} #{command.index}: curseur "
                    f"{result.cursor}, attendu {command.next_cursor}")
            return result
        if result.status in (DeliveryStatus.DEFERRED,
                             DeliveryStatus.INVENTORY_FULL):
            if result.cursor != command.cursor:
                raise BackendContractError(
                    f"{result.status.value} #{command.index}: curseur avance "
                    f"a {result.cursor}")
            return result
        if result.status is DeliveryStatus.UNCERTAIN:
            return self._reconcile_unknown(command,
                                           result.detail or "issue native inconnue")
        raise BackendContractError(
            f"statut backend interdit: {result.status.value}")

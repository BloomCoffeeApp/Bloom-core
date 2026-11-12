"""Order state machine: one declarative flow (strategy) per channel, chosen at runtime by the order.

    caja       received(confirmado) → preparing → ready → delivered            (paid at checkout: a sale)
    mesa       pending(pedido) → received(confirmado) → preparing → ready → delivered(servido) → paid
    take_away  pending → accepted → awaiting_pay → paid → preparing → ready → delivered(retirado)
    delivery   pending → accepted → awaiting_pay → paid → preparing → ready → dispatched(enviado) → delivered
               exits (online): rejected (reason), expired (unpaid after N min), cancelled (+ refund)
               cash on delivery/pickup skips the payment step: accepted → preparing

Each `OrderFlow` declares its states in order, the allowed transitions (state → next states), the
actions each state offers to the screen (buttons, built from data by the frontend) and optional
guards/effects per transition. `orders.transition()` is the single entry point: it validates the move
against the order's flow, runs guards and effects in the caller's transaction, audits and raises 409.

Rules:
- `via="ui"`: only moves offered as an action of the current state (and whose guard passes).
- `via="system"`: any declared transition (payment approval, expiry, tab charge, a chained step).
- Effects keyed by (from, to); "*" matches any state. Core effects (timestamps, bar queue, tabs) are
  declared here; modules add theirs with `on(...)` / `guard(...)` (e.g. Pro online orders: create the
  charge on accepted → awaiting_pay, refund when a paid order is cancelled).
Adding a channel = one more `OrderFlow` in FLOWS (+ a line in `flow_key`).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm import Session

    from app.models import Order, User


@dataclass
class Ctx:
    """What a guard/effect gets besides the order."""

    db: "Session"
    actor: "User | None"
    frm: str
    to: str
    reason: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    via: str = "ui"


Guard = Callable[["Order", Ctx], str | None]  # returns an error message (409) or None
Effect = Callable[["Order", Ctx], None]


@dataclass(frozen=True)
class Action:
    """A button the order screen shows for a state. `needs`: eta (accept dialog), reason (required),
    reason_optional, confirm. `place`: main (footer) | menu (⋮). `tone`: primary | success | secondary |
    outline | danger."""

    to: str
    label: str
    tone: str = "primary"
    place: str = "main"
    needs: str | None = None
    icon: str | None = None
    label_if_paid: str | None = None  # e.g. «Cancelar y devolver»


@dataclass(frozen=True)
class State:
    key: str
    label: str
    # Board column: confirm | payment | queue | preparing | ready | done
    column: str
    actions: tuple[Action, ...] = ()


@dataclass
class OrderFlow:
    key: str
    label: str
    states: tuple[State, ...]
    transitions: dict[str, frozenset[str]]
    guards: dict[tuple[str, str], list[Guard]] = field(default_factory=dict)
    effects: dict[tuple[str, str], list[Effect]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        keys = {s.key for s in self.states}
        for frm, tos in self.transitions.items():
            assert frm in keys and tos <= keys, f"{self.key}: unknown state in {frm} → {tos}"
        for s in self.states:
            for a in s.actions:
                assert a.to in self.transitions.get(s.key, frozenset()), f"{self.key}: action {s.key} → {a.to} not allowed"

    def state(self, key: str) -> State:
        return next(s for s in self.states if s.key == key)

    def allows(self, frm: str, to: str) -> bool:
        return to in self.transitions.get(frm, frozenset())

    def _matching(self, table: dict[tuple[str, str], list], frm: str, to: str) -> list:
        return [*table.get(("*", to), []), *table.get((frm, to), [])]

    def check(self, o: "Order", ctx: Ctx) -> str | None:
        for g in self._matching(self.guards, ctx.frm, ctx.to):
            msg = g(o, ctx)
            if msg:
                return msg
        return None

    def run_effects(self, o: "Order", ctx: Ctx) -> None:
        for fx in self._matching(self.effects, ctx.frm, ctx.to):
            fx(o, ctx)

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "states": [
                {"key": s.key, "label": s.label, "column": s.column, "next": sorted(self.transitions.get(s.key, ())),
                 "actions": [action_out(a, False) for a in s.actions]}
                for s in self.states
            ],
        }


def action_out(a: Action, paid: bool) -> dict[str, Any]:
    return {"to": a.to, "label": (a.label_if_paid if paid and a.label_if_paid else a.label), "tone": a.tone,
            "place": a.place, "needs": a.needs, "icon": a.icon}


def _t(**kw: set[str]) -> dict[str, frozenset[str]]:
    return {k: frozenset(v) for k, v in kw.items()}


# ---------------------------------------------------------------- shared actions

START = Action("preparing", "Empezar", icon="chef")
READY_MAIN = Action("ready", "Listo", tone="success", icon="check")
READY_SHORTCUT = Action("ready", "Listo", tone="outline", icon="check")
BACK_TO_PREP = Action("preparing", "Volver a «En preparación»", place="menu", icon="undo")
CANCEL = Action("cancelled", "Cancelar pedido", tone="danger", place="menu", needs="reason_optional", icon="x",
                label_if_paid="Cancelar y devolver")

_KITCHEN_STATES = (
    State("preparing", "En preparación", "preparing",
          (READY_MAIN, Action("received", "Volver a «Nuevo»", place="menu", icon="undo"), CANCEL)),
    State("ready", "Listo", "ready", (Action("delivered", "Entregado", tone="secondary", icon="hand"), BACK_TO_PREP)),
)

CAJA = OrderFlow(
    "caja", "Caja (mostrador)",
    states=(
        State("received", "Confirmado", "queue", (START, READY_SHORTCUT, CANCEL)),
        *_KITCHEN_STATES,
        State("delivered", "Entregado", "done", (Action("ready", "Volver a «Listo»", place="menu", icon="undo"),)),
        State("cancelled", "Cancelado", "done"),
    ),
    transitions=_t(
        received={"preparing", "ready", "cancelled"},
        preparing={"ready", "received", "cancelled"},
        ready={"delivered", "preparing"},
        delivered={"ready"},
    ),
)

MESA = OrderFlow(
    "mesa", "Mesa (QR)",
    states=(
        State("pending", "Pedido", "confirm", (
            Action("received", "Confirmar", icon="check"),
            Action("cancelled", "Rechazar", tone="outline", needs="reason_optional", icon="x"),
        )),
        State("received", "Confirmado", "queue", (START, READY_SHORTCUT, CANCEL)),
        _KITCHEN_STATES[0],
        State("ready", "Listo", "ready", (Action("delivered", "Servido", tone="secondary", icon="hand"), BACK_TO_PREP)),
        State("delivered", "Servido", "done", (Action("ready", "Volver a «Listo»", place="menu", icon="undo"),)),
        State("paid", "Pagado", "done"),
        State("cancelled", "Cancelado", "done"),
    ),
    transitions=_t(
        pending={"received", "cancelled"},
        received={"preparing", "ready", "cancelled"},
        preparing={"ready", "received", "cancelled"},
        ready={"delivered", "preparing"},
        delivered={"ready", "paid"},  # paid: the tab was charged (system)
        paid={"delivered"},  # the tab's sale was voided: the table owes it again (system)
    ),
)


def _online(key: str, label: str, delivery: bool) -> OrderFlow:
    done_label = "Entregado" if delivery else "Retirado"
    ready_actions = (
        (Action("dispatched", "Enviado", tone="secondary", icon="bike"),) if delivery
        else (Action("delivered", "Retirado", tone="secondary", icon="hand"),)
    ) + (BACK_TO_PREP, CANCEL)
    states = [
        State("pending", "Pedido", "confirm", (
            Action("accepted", "Aceptar", needs="eta", icon="check"),
            Action("rejected", "Rechazar", tone="outline", needs="reason", icon="x"),
        )),
        State("accepted", "Aceptado", "queue", (START, READY_SHORTCUT, CANCEL)),
        State("awaiting_pay", "Pago pendiente", "payment", (
            Action("paid", "Pago recibido", tone="success", needs="confirm", icon="banknote"),
            Action("cancelled", "Cancelar pedido", tone="danger", place="menu", needs="reason_optional", icon="x"),
        )),
        State("paid", "Pagado", "queue", (START, READY_SHORTCUT, CANCEL)),
        State("preparing", "En preparación", "preparing", (
            READY_MAIN,
            Action("paid", "Volver a «Nuevo»", place="menu", icon="undo"),
            Action("accepted", "Volver a «Nuevo»", place="menu", icon="undo"),
            CANCEL,
        )),
        State("ready", "Listo", "ready", ready_actions),
    ]
    if delivery:
        states.append(State("dispatched", "Enviado", "ready", (
            Action("delivered", "Entregado", tone="secondary", icon="hand"),
            Action("ready", "Volver a «Listo»", place="menu", icon="undo"),
        )))
    states += [
        State("delivered", done_label, "done", (
            Action("dispatched" if delivery else "ready", "Deshacer «%s»" % done_label, place="menu", icon="undo"),
        )),
        State("rejected", "Rechazado", "done"),
        State("expired", "Vencido", "done"),
        State("cancelled", "Cancelado", "done"),
    ]
    transitions = dict(
        pending={"accepted", "rejected"},
        accepted={"awaiting_pay", "preparing", "ready", "cancelled"},
        awaiting_pay={"paid", "expired", "cancelled"},
        paid={"preparing", "ready", "cancelled"},
        preparing={"ready", "accepted", "paid", "cancelled"},
        ready={"dispatched" if delivery else "delivered", "preparing", "cancelled"},
        delivered={"dispatched" if delivery else "ready"},
    )
    if delivery:
        transitions["dispatched"] = {"delivered", "ready"}
    return OrderFlow(key, label, states=tuple(states), transitions=_t(**transitions))


TAKE_AWAY = _online("take_away", "Take away (menú online)", delivery=False)
DELIVERY = _online("delivery", "Delivery (menú online)", delivery=True)

FLOWS: dict[str, OrderFlow] = {f.key: f for f in (CAJA, MESA, TAKE_AWAY, DELIVERY)}


def flow_key(o: "Order") -> str:
    """The order's origin picks its flow."""
    if o.source == "table":
        return "mesa"
    if o.source == "online":
        return "delivery" if o.channel == "delivery" else "take_away"
    return "caja"


def flow_of(o: "Order") -> OrderFlow:
    return FLOWS[flow_key(o)]


# ---------------------------------------------------------------- extension points


def on(flows: str | tuple[str, ...], frm: str, to: str, fn: Effect) -> None:
    """Registers an effect (idempotent) for (from, to) in one or more flows."""
    for key in (flows,) if isinstance(flows, str) else flows:
        lst = FLOWS[key].effects.setdefault((frm, to), [])
        if fn not in lst:
            lst.append(fn)


def guard(flows: str | tuple[str, ...], frm: str, to: str, fn: Guard) -> None:
    for key in (flows,) if isinstance(flows, str) else flows:
        lst = FLOWS[key].guards.setdefault((frm, to), [])
        if fn not in lst:
            lst.append(fn)


def describe_all() -> list[dict[str, Any]]:
    return [f.describe() for f in FLOWS.values()]

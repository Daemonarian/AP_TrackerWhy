import logging
from typing import TYPE_CHECKING
from MultiServer import mark_raw
from worlds.tracker import UT_VERSION_TUPLE
from worlds.tracker_addons import register_function
from .solver import find_minimal_items_for_location

if TYPE_CHECKING:
    from worlds.tracker.TrackerClient import TrackerCommandProcessor

if not UT_VERSION_TUPLE >= (0, 3, 1):
    raise ImportError("Universal Tracker Why Addon 1.0.0 is missing compatible UT")

logger = logging.getLogger("Client")

@mark_raw
def why(self: "TrackerCommandProcessor", location_name: str = "") -> None:
    """Find a minimal set of additional progression items needed to reach a location."""
    if not self.ctx.game:
        logger.info("Not yet loaded into a game")
        return

    struct = self.ctx.updateTracker()
    multiworld = self.ctx.tracker_core.multiworld
    player_id = self.ctx.tracker_core.player_id

    if multiworld is None or player_id is None:
        logger.info("Universal Tracker multiworld is not initialized yet.")
        return

    if not location_name or not location_name.strip():
        logger.info("Usage: /why <location_name>")
        return

    assert struct.state

    try:
        messages = find_minimal_items_for_location(
            self.ctx,
            multiworld,
            player_id,
            struct.state,
            location_name.strip(),
        )
        for msg in messages:
            logger.info(msg)
    except Exception as exc:
        logger.exception("Error while running /why solver:")
        logger.error(f"Error evaluating location logic: {exc}")


register_function("why", why)
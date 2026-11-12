from collections import Counter, deque
import difflib
from typing import Dict, List, Optional, Tuple
from BaseClasses import CollectionState, Item, Location, MultiWorld


MAX_BFS_EVALUATIONS = 2000
MAX_SOLUTIONS_TO_RETURN = 3


def _get_uncollected_progression_pool(
    base_state: CollectionState, multiworld: MultiWorld, player: int
) -> Dict[str, List[Item]]:
    """
    Returns a dictionary of remaining uncollected progression items for the player,
    subtracting copies already present in Universal Tracker's current CollectionState.
    """
    all_prog_items: Dict[str, List[Item]] = {}
    for item in multiworld.get_items():
        if item.player == player and item.advancement and item.code is not None:
            all_prog_items.setdefault(item.name, []).append(item)

    uncollected_by_name: Dict[str, List[Item]] = {}
    player_prog_counts = base_state.prog_items[player]

    for name, items in all_prog_items.items():
        already_have = player_prog_counts.get(name, 0)
        remaining_copies = len(items) - already_have
        if remaining_copies > 0:
            uncollected_by_name[name] = items[:remaining_copies]

    return uncollected_by_name


def _resolve_location(
    multiworld: MultiWorld, player: int, query: str
) -> Tuple[Optional[Location], List[str]]:
    """Finds a Location by exact, case-insensitive, or fuzzy match."""
    player_locations = multiworld.get_locations(player)
    loc_by_name = {
        loc.name: loc for loc in player_locations if loc.address is not None
    }

    # 1. Exact match
    if query in loc_by_name:
        return loc_by_name[query], []

    # 2. Case-insensitive exact match
    query_lower = query.lower()
    for name, loc in loc_by_name.items():
        if name.lower() == query_lower:
            return loc, []

    # 3. Substring / Fuzzy match
    substring_matches = [name for name in loc_by_name if query_lower in name.lower()]
    if len(substring_matches) == 1:
        return loc_by_name[substring_matches[0]], []
    if len(substring_matches) > 1:
        return None, substring_matches[:8]

    fuzzy_matches = difflib.get_close_matches(
        query, list(loc_by_name.keys()), n=5, cutoff=0.45
    )
    return None, fuzzy_matches


def _can_reach_with_items(
    base_state: CollectionState,
    location: Location,
    item_pool_by_name: Dict[str, List[Item]],
    counts: Dict[str, int],
) -> bool:
    """Clones base_state, adds the specified item counts, sweeps events, and tests reachability."""
    test_state = base_state.copy()
    for name, count in counts.items():
        items = item_pool_by_name[name]
        for i in range(count):
            test_state.collect(items[i], prevent_sweep=True)
    test_state.sweep_for_events()
    return location.can_reach(test_state)


def _format_item_counts(counts: Dict[str, int]) -> str:
    parts = []
    for name in sorted(counts.keys()):
        cnt = counts[name]
        if cnt == 1:
            parts.append(name)
        else:
            parts.append(f"{cnt}x {name}")
    return ", ".join(parts) if parts else "None"


def find_minimal_items_for_location(
    ctx,
    multiworld: MultiWorld,
    player: int,
    current_state: CollectionState,
    location_query: str,
) -> List[str]:
    location, suggestions = _resolve_location(multiworld, player, location_query)
    if location is None:
        if suggestions:
            return [
                f"Location '{location_query}' not found. Did you mean: "
                + ", ".join(f"'{s}'" for s in suggestions)
            ]
        return [f"Location '{location_query}' not found in player slot."]

    base_state = current_state.copy()

    # Step 0: Check if already reachable in Universal Tracker's state
    if (
        location.name in getattr(ctx.tracker_core, "locations_available", [])
        or location.can_reach(base_state)
    ):
        return [
            f"[{location.name}] is ALREADY reachable in logic with your current items!"
        ]

    uncollected_by_name = _get_uncollected_progression_pool(
        base_state, multiworld, player
    )

    # Step 1: Verify solvability with ALL remaining progression items
    all_counts = {name: len(items) for name, items in uncollected_by_name.items()}
    if not _can_reach_with_items(
        base_state, location, uncollected_by_name, all_counts
    ):
        return [
            f"[{location.name}] is UNREACHABLE even with all remaining progression items in the pool "
            "(check may be disabled by YAML options or locked behind an unfulfilled condition)."
        ]

    # Step 2: Mandatory Bottleneck Extraction & Candidate Pruning
    mandatory_counts: Dict[str, int] = {}
    optional_candidates: Dict[str, List[Item]] = {}

    for name, items in uncollected_by_name.items():
        total_copies = len(items)
        test_counts = dict(all_counts)
        del test_counts[name]

        if not _can_reach_with_items(
            base_state, location, uncollected_by_name, test_counts
        ):
            # Item is a strict bottleneck! Find exact minimum copies required in FullState.
            req_copies = total_copies
            for k in range(1, total_copies):
                test_counts[name] = k
                if _can_reach_with_items(
                    base_state, location, uncollected_by_name, test_counts
                ):
                    req_copies = k
                    break
            mandatory_counts[name] = req_copies

            for i in range(req_copies):
                base_state.collect(items[i], prevent_sweep=True)

            leftover = items[req_copies:]
            if leftover:
                optional_candidates[name] = leftover
        else:
            optional_candidates[name] = items

    base_state.sweep_for_events()

    if location.can_reach(base_state):
        return [
            f"[{location.name}] requires: {_format_item_counts(mandatory_counts)}"
        ]

    # Step 3: Bounded BFS over remaining optional candidates
    candidate_names = sorted(optional_candidates.keys())
    queue = deque([Counter()])
    visited = {frozenset()}
    solutions: List[Counter] = []
    evaluations = 0
    found_depth: Optional[int] = None

    while queue and evaluations < MAX_BFS_EVALUATIONS:
        current_combo = queue.popleft()
        current_depth = sum(current_combo.values())

        if found_depth is not None and current_depth > found_depth:
            break

        for name in candidate_names:
            if current_combo[name] >= len(optional_candidates[name]):
                continue

            next_combo = current_combo.copy()
            next_combo[name] += 1
            canonical_key = frozenset(next_combo.items())

            if canonical_key in visited:
                continue
            visited.add(canonical_key)

            if any(all(next_combo[k] >= sol[k] for k in sol) for sol in solutions):
                continue

            evaluations += 1
            if _can_reach_with_items(
                base_state, location, optional_candidates, next_combo
            ):
                solutions.append(next_combo)
                if found_depth is None:
                    found_depth = current_depth + 1
                if len(solutions) >= MAX_SOLUTIONS_TO_RETURN:
                    break
            else:
                if found_depth is None:
                    queue.append(next_combo)

        if len(solutions) >= MAX_SOLUTIONS_TO_RETURN:
            break

    # Step 4: Format BFS Solutions if found
    if solutions:
        output_lines = [f"[{location.name}] can be reached with:"]
        for idx, sol in enumerate(solutions, 1):
            combined = Counter(mandatory_counts) + sol
            output_lines.append(
                f"  Option {idx}: {_format_item_counts(dict(combined))}"
            )
        return output_lines

    # Step 5: Graceful Fallback -> Greedy Reverse-Deletion from FullState
    greedy_counts = {name: len(items) for name, items in optional_candidates.items()}
    for name in candidate_names:
        while greedy_counts.get(name, 0) > 0:
            greedy_counts[name] -= 1
            if greedy_counts[name] == 0:
                del greedy_counts[name]

            if not _can_reach_with_items(
                base_state, location, optional_candidates, greedy_counts
            ):
                greedy_counts[name] = greedy_counts.get(name, 0) + 1
                break

    combined_greedy = Counter(mandatory_counts) + Counter(greedy_counts)
    return [
        f"[{location.name}] is deep in logic; minimal required set found via reverse-pruning:",
        f"  Requires: {_format_item_counts(dict(combined_greedy))}",
    ]
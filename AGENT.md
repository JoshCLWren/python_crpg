AGENT.md

A practical guide to the agent system for a Python, tile based, Eye of the Beholder style CRPG. Read this before adding new creatures, behaviors, or party automation.

Game style assumptions, locked
	•	Grid movement, one tile per step, 90 degree turns, no diagonals.
	•	Real time with a fixed tick, action cooldowns in seconds, input buffer supports rapid arrow taps.
	•	Party is a 2x2 formation in a single cell. Front row can melee. Back row needs reach, ranged, or spells. Slot based reach checks.
	•	Single shared viewport. Line of sight originates from the party cell, facing controls field of view.
	•	Interactables live on tiles in front of the party, buttons, levers, keyholes, slots, doors, and puzzle panels that toggle tile states.
	•	Inventory is drag and drop. Items can live on world tiles. Quick slots map to UI buttons.
	•	Enemies use the same grid. Simple aggro with leash timers, prefer to move to side tiles to flank.
	•	Attacks have windup and recovery. Stutter stepping is possible but not perfect.
	•	Auto step and auto turn are supported. Auto stops on enemy contact or puzzle.

Goals and non goals
	•	Goals, readable AI, deterministic simulation for tests, mod friendly data, fast grid pathfinding, low CPU per tick.
	•	Non goals, machine learning, network play, cinematic scripting.

Terms
	•	Agent: anything that can sense, decide, and act.
	•	Party: the player team as a composite agent with formation rules.
	•	NPC: non player agents, creatures and interactables with logic.
	•	Blackboard: per agent key value memory.
	•	Tick: one simulation step with fixed delta time.

Architecture overview
	•	Core loop, perceive -> think -> plan -> act.
	•	Components, Perception, Memory, Planner, ActionQueue, Locomotion, Combat, Dialogue.
	•	Data flow, world to sensors to working memory to planner to actions to world updates.
	•	Determinism, fixed tick rate, seeded RNG, no wall clock access inside AI.

Agent lifecycle
	1.	awake() construct components and seed RNG.
	2.	perceive(world) collect observations.
	3.	update_memory(observations) merge, decay, forget.
	4.	plan() pick behavior via Behavior Tree or GOAP helpers.
	5.	enqueue_actions(plan).
	6.	act(world) perform one action, handle cooldowns and failures.
	7.	post_update() cleanups and event publishing.

Agent interface

class Agent:
    def perceive(self, world, dt): ...
    def think(self, dt): ...
    def act(self, world, dt): ...
    def debug_state(self) -> dict: ...

Perception
	•	Tile grid field of view using shadow casting. Hearing by radius with falloff. Optional scent trails.
	•	Visibility flags, lit, dark, blocked by doors or walls, special tiles such as pits and teleports.
	•	Threat classes, hostile, neutral, friendly.
	•	Performance, cache FOV per tile and facing, invalidate on movement or door state change.

Memory
	•	Short term, last seen positions with timestamps.
	•	Long term, known doors, levers, traps, secret walls, safe spots.
	•	Emotional state, fear, anger, curiosity as floats in range 0 to 1.
	•	Decay and forgetting thresholds with simple linear falloff.

Decision making
	•	Default planner is Behavior Trees with small goal helpers for convenience.
	•	Priority order, survive, attack, defend, explore, idle.
	•	Cooldowns per behavior and per action.
	•	Reaction time is configurable per agent to avoid perfect play.

Behavior Trees layout
	•	Top level selectors, Combat, Alert, Patrol, Idle.
	•	Reusable leaves, MoveTo, FaceTarget, Attack, DrinkPotion, OpenDoor, Flee, SearchNoise, PullLever, UseItem, CastSpell.
	•	Decorators, UntilSuccess, UntilFail, TimeLimit, Inverter, WithBlackboardKey.
	•	Authoring in YAML or TOML with node refs and parameters.

GOAP helpers, optional
	•	Goals, Alive, EnemyDefeated, Escape, PatrolRouteDone.
	•	Actions carry preconditions, effects, and a cost function. A* over world state atoms.

Movement and pathfinding
	•	Grid A* with Manhattan heuristics and tie breaking.
	•	Door handling, try open, bash if hostile, skip if locked unless key present.
	•	Party formation, maintain 2x2, keep back row behind front row, swap on command.
	•	Corner cases, moving floors, pits, teleports, squeeze if size allows.
	•	Stuck detection with local replans and short detours.

Combat AI
	•	Target selection, threat score based on proximity, damage taken, party caster priority, and low HP preference.
	•	Melee, approach, face, attack, step back if surrounded.
	•	Ranged, maintain distance band, kite, avoid friendly fire by line checks.
	•	Spells, buffs before contact, open with debuffs, follow with damage, conserve mana for elites.
	•	Items, potions below HP threshold, scrolls when out of mana, track limited ammo.
	•	Status handling, flee when fear is high, hold when rooted, swap weapons if webbed.

Exploration AI
	•	Patrol routes as room graphs with waypoints.
	•	Search behavior investigates last known noise or sighting.
	•	Secret finding with probabilistic checks near suspicious walls and mosaics.
	•	Door and lever rules, safe flips by faction and zone.
	•	Trap awareness, remember trigger tiles, add path cost penalties through danger.

Dialogue and interaction
	•	Dialogue triggers by proximity, faction, or quest flags.
	•	Reputation checks gate greetings, trades, and hostility.
	•	Conversation actions can set blackboard flags, unlock doors, or toggle hostility.

Party automation
	•	Auto step and wall following, left or right, stop on enemy or secret detection.
	•	Auto map integration picks the next unexplored frontier with a Dijkstra map.
	•	Loot rules, weight limits, auto distribute to best carrier and class needs.
	•	Rest logic, only in safe zones, watch rotation, ambush handling.

Data definitions
	•	agent.yaml, stats, class, level, skills, spells, resistances, senses, inventory slots, behavior preset, faction, voice lines.
	•	behavior/*.yaml, BT nodes and parameters.
	•	loot_tables/*.yaml, item drops.
	•	factions.yaml, relationships, hate, neutral, friendly.
	•	Versioning with a semver field and migration notes.

Actions API

class Action(Protocol):
    def check(self, agent, world) -> bool: ...
    def perform(self, agent, world, dt) -> "Result": ...
    def cost(self, agent, world) -> float: ...

	•	Common actions, Move, Turn, Use, Attack, Cast, Interact, Wait.
	•	Results, Success, Fail, Running, with reason codes for debugging.

Events and messaging
	•	Event bus, on_tile_entered, on_door_opened, on_noise, on_spell_cast, on_agent_down, on_item_picked.
	•	Components subscribe. No direct cross agent calls.
	•	Queues drain during act to keep determinism.

Config and tuning
	•	Difficulty curves scale HP, damage, and behavior sets at higher levels.
	•	Global caps, max chase time, max simultaneous thinkers per tick.
	•	RNG seeds per dungeon and per agent. Save files record seeds.

Performance guide
	•	Tick budget targets, keep AI under a small fixed budget per frame.
	•	Spatial partitioning by room or zone to cut perception cost.
	•	Path cache per agent and per target. Invalidate on door changes.
	•	Profiling, cProfile entry points and flamegraph scripts.

Debugging
	•	Overlays, show FOV, current path, target, and BT node stack.
	•	Console commands, ai.pause, ai.step, ai.inspect <id>, ai.seed <n>, ai.fov.
	•	Logging, per agent JSON lines, last N actions in a ring buffer.
	•	Repro harness, load save, run N ticks, compare world hash.

Testing
	•	Unit tests for leaf actions and sensors.
	•	Golden tests for BTs with fixed seeds.
	•	Scenario tests, arena fights, door puzzles, trap rooms.
	•	Contract tests, every action is idempotent on fail and reversible when possible.

Save and load
	•	Snapshot blackboard, BT node pointers, RNG state, action queue, cooldowns.
	•	Backward compatible migrations with defaults for old fields.

Modding
	•	Behavior packs add new leaf nodes through entry points.
	•	Data validation and lint rules catch missing nodes, items, or bad faction names.
	•	No arbitrary code allowed inside data files.

Security and fairness
	•	AI sees only what sensors allow. No hidden map access.
	•	Cheating toggles exist for developers only.

New creature checklist
	1.	Create agent.yaml.
	2.	Choose a behavior preset or write a new BT file.
	3.	Define loot table and faction relations.
	4.	Add sprites and sounds.
	5.	Write tests for two core behaviors.
	6.	Spawn in a test room and verify overlays.
	7.	Tune perception, aggression, and item use.
	8.	Update bestiary docs.

Known edge cases
	•	Teleports cancel paths and require immediate replan.
	•	Doors closing during movement trigger rechecks to avoid jitter.
	•	Multi tile enemies need alignment and rotation care at corners.
	•	Moving floors change path costs and invalidate caches.

File layout

/ai/
  agent.py
  blackboard.py
  perception.py
  planner_bt/
    nodes/*.py
    loader.py
  actions/*.py
  data/
    agents/*.yaml
    behavior/*.yaml
    factions.yaml
    loot_tables/*.yaml
/tests/ai/
  ...

Integration points
	•	World API for tile queries, occupancy, door state, light, noise emitters, and interactables.
	•	Rendering for debug layers.
	•	Audio cues from actions and events.
	•	Scripting hooks for quest flags that influence behavior.

Coding standards
	•	Keep nodes small and pure where possible.
	•	No globals. Pass RNG through.
	•	Type hints everywhere. MyPy clean.
	•	Clear names and short files.

Example behavior preset

# data/behavior/goblin_scout.yaml
root:
  selector:
    - sequence: [sense_threat, flee_if_outnumbered]
    - sequence: [see_enemy, keep_distance, ranged_attack]
    - sequence: [hear_noise, investigate_last_noise]
    - patrol
nodes:
  sense_threat: check_enemies_within: {radius: 3}
  flee_if_outnumbered: flee_to_known_safe: {max_secs: 4}
  see_enemy: has_los_to_enemy: {}
  keep_distance: kite: {min: 3, max: 5}
  ranged_attack: shoot: {cooldown_s: 2.0}
  hear_noise: heard_recent_noise: {since_s: 6}
  investigate_last_noise: move_to: {bb_key: last_noise_pos}
  patrol: follow_waypoints: {loop: true}

Authoring tips
	•	Start simple, add one behavior at a time.
	•	Prefer data knobs over code for tuning.
	•	Watch several full fights before changing numbers.

Appendix, references
	•	Algorithms, shadow casting FOV, A*, Dijkstra maps, Behavior Tree patterns.
	•	Attributions for third party ideas and assets.

---
name: nw-hybrid-paradigm
description: Hybrid paradigm decision guide - function or object, where per-run state lives, time and ids as ports, procedures disguised as classes
user-invocable: false
disable-model-invocation: true
---

# Hybrid Paradigm -- Function or Object?

**Applies when** the project's paradigm is hybrid. That is the default when CLAUDE.md has no `## Development Paradigm` section, or that section says hybrid. In an explicitly object-oriented project, services may be classes; the port, state and time rules below still apply.

The hybrid paradigm is **functional in the small and object-oriented in the large**:
- Values and rules are immutable and pure.
- Use cases are stateless functions.
- Structure is objects: ports are interfaces, adapters are classes, and each bounded context has a facade.

Language skills (e.g. `nw-kotlin`) supply the idioms. `nw-naming` names whatever comes out of this guide.

Cross-references: [naming](../nw-naming/SKILL.md) | [kotlin](../nw-kotlin/SKILL.md) | [hexagonal-testing](../nw-hexagonal-testing/SKILL.md)

The question to ask is never "should this be a class?". It is "**what is this thing?**" Answer it before you write anything, because the answer decides both the shape and the name.

## The Decision

Work down the list and stop at the first match.

| # | It is... | Shape | Example |
|---|---|---|---|
| 1 | A fact or measurement with no identity, equal when its values are equal | **Value object**: immutable, invariants checked at construction | `GameSignature`, `SteamAppId`, `Money` |
| 2 | Something with identity that lives through changes | **Entity / aggregate**: immutable data plus pure transition functions that return a new state | `Account`, `GameLibrary` |
| 3 | A rule, calculation or transformation of values | **Pure function**, top-level or on the value it is about | `referencedIds(game)`, `signature.matches(other)` |
| 4 | Something the core needs from the outside world: storage, time, ids, an external API, randomness | **Port**: an interface in business language | `StoredRecordsRepository`, `Clock`, `IdentityMint`, `GameCatalog` |
| 5 | The technical fulfilment of a port: SQL, HTTP, files, the system clock | **Adapter**: a class with constructor injection, named technology + port | `SqliteStoredRecordsRepository`, `IgdbGameCatalog`, `SystemClock` |
| 6 | A use case: a sequence of steps a user or system asks for | **Service function**: top-level, takes a command plus ports as parameters, returns an outcome | `pullSteamLibrary(command, steamLibrary, catalog, records, clock)` |
| 7 | The set of use cases one bounded context offers to the outside | **Driving facade**: an interface plus an `…App` implementation that delegates to the service functions | `Accounts` / `AccountsApp` |
| 8 | Wiring of concrete adapters | **Composition root**: a plain `bootstrap…()` function | `bootstrapIgdbCli(settings)` |

Two things are never objects of their own:
- **A procedure.** A sequence of steps is a function (row 6), or several small private functions in the same file.
- **A grab-bag of helpers.** Helpers go next to the concept they serve, or become top-level functions in a file named after that concept.

## Tests for "this should be a function"

These tests apply to classes that **implement no port and are not a facade**. Adapters (row 5) and facades (row 7) are exempt: a constructor holding dependencies is exactly their shape.

If any test is true, the class is a procedure in disguise. Dismantle it into functions.

1. **Named after an action**, not a thing: `Pull`, `Lookup`, `Sync`, `Import`, `Fetcher`, `Processor`. See `nw-naming` Rule 3.
2. **One public method**, and its fields are only the dependencies it was constructed with. That is a function with its parameters moved into a constructor.
3. **Created, used once and thrown away** inside a single call (`Thing(deps).run(input)`).
4. **Its fields are only ports plus per-call bookkeeping** (counters, "already done" sets, accumulators). The bookkeeping is local state of one call. Pass it explicitly, or give it a home (see "Where state lives").
5. **You can't say what one instance *is*** without describing what it *does*.

## Tests for "this should be an object"

1. **It stands for something real**: a domain thing (value or entity), or an outside capability behind a port.
2. **It owns a resource or lifecycle**: a connection, a file handle, a cache, a token that renews itself. That is an adapter, and it usually implements `AutoCloseable` or its language equivalent.
3. **It has several cohesive operations over the same data or resource**: `store`, `find`, `count` on one repository.
4. **It must be replaceable**: a fake in tests, or another technology later. That makes it a port (interface) with an adapter (class).

## Where state lives

- **Domain state** belongs to immutable values and entities. A change returns a new value.
- **Persistent state** goes behind a repository port.
- **Per-run state** is often disguised as a field: "ids already fetched", "pages seen", "errors so far". It means one of two things:
  - It is part of the use case's own data flow. Keep it as a local value or accumulator inside the service function, or fold it through the steps.
  - Or it is really a question about stored data ("is this record already stored?"). Then ask the repository (`records.storedIds(endpoint)`, `records.isStored(endpoint, id)`).

  Never hide it in a "service" object so that the service becomes stateful.
- **Configuration** is resolved once at the driving edge into a value (`Settings`) and passed in. Services never read files, the environment or system properties.

## Time, identity and randomness are ports

A service never reads the system clock, generates a UUID or draws a random number directly. Doing so makes behaviour untestable and couples the core to a platform type.

- **Search the project first.** Look for an existing `Clock`, `IdentityMint` or `RandomSource` port in `ports/` or shared modules, and reuse it.
- **If none can be reached**, because of a module boundary, inject the language's neutral abstraction instead of calling the platform:

  | Language | Inject | Never call in a service |
  |---|---|---|
  | Kotlin | `kotlin.time.Clock` | `java.time.Clock`, `Instant.now()`, `System.currentTimeMillis()`, `UUID.randomUUID()` |
  | Python | a `Clock` protocol or a `Callable[[], datetime]` | `datetime.now()`, `time.time()`, `uuid.uuid4()` |
  | TypeScript | a `Clock` interface | `Date.now()`, `new Date()`, `crypto.randomUUID()` |

  `kotlin.time.Clock` is stable in the standard library from Kotlin 2.3. On 2.1.20 to 2.2.x it needs `@OptIn(ExperimentalTime::class)`. From kotlinx-datetime 0.7, `kotlinx.datetime.Clock` is a deprecated alias of it.

  Mention in the handoff that a shared port might be worth extracting.
- **Measuring elapsed time** (rate limits, timeouts) is a different port from reading the date (a monotonic clock vs a wall clock). Don't conflate them.

## Dismantling a Disguised Procedure -- Worked Example

The first draft of a CLI that pulls IGDB records for a Steam library looked like this:

```kotlin
class IgdbPull(lookup: IgdbLookup, store: SeedStore, clock: java.time.Clock)   // action noun, java.time
{
    private val storedIds = StoredIds()                                        // per-run bag of state
    suspend fun pull(appIds: Collection<Int>): ServiceResult<...> { ... }      // the only public method
}
class IgdbLookup(client: IgdbClient) { matchSteamApps(...); fetchByIds(...) }  // action noun, implements no port
class StoredIds { notYetStored(...); markRequested(...) }                      // bag, no concept
```

Ask "what is it?" for each piece:

| Piece | What it really is | Becomes |
|---|---|---|
| `IgdbPull.pull` | The use case "pull my Steam library's games" | `pullSteamLibrary(command: PullSteamLibraryCommand, steamLibrary: SteamLibrary, catalog: GameCatalog, records: StoredRecordsRepository, clock: Clock)` |
| Following references | A rule over game JSON | Pure function `referencedIds(records, referenceTable)` |
| `IgdbLookup` | Our view of IGDB as a game catalog, an outside capability | Port `GameCatalog` (`steamMatches`, `recordsByIds`) + adapter `IgdbGameCatalog(client)` |
| `SeedStore` + `StoredIds` | Storage of raw IGDB records, and the question "is it stored yet?" | Port `StoredRecordsRepository` (`store`, `storedIds`) + adapter `SqliteStoredRecordsRepository` |
| `java.time.Clock` | Wall-clock time for `fetched_at` | The project's `Clock` port, or injected `kotlin.time.Clock` when no project port can be reached |

The result has no stateful service object. The use case is a function, and the objects are the things the domain actually talks about.

## Anti-Patterns -- Reject on Sight

| Anti-pattern | Instead |
|---|---|
| Class named after an action that implements no port (`IgdbPull`, `DataSync`, `ReportGenerator`) | A service function, or a port + adapter if it reaches outside |
| Stateful service class (ports + bookkeeping fields + `run()`) | A top-level function. Bookkeeping becomes local values or a repository query |
| `Helper` / `Utils` / `Manager` classes | Functions next to the concept they serve |
| Value logic in a service ("compute X from this record") | A pure function on or near the value |
| Platform clock, UUID or random calls inside services | An injected port, reused from the project when one exists |
| A wrapper class that only renames a library call | Use the library in the adapter directly, or make it a port if the core needs it |
| An object created and discarded within one call | A function |

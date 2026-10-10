---
name: nw-atdd-dsl
description: Acceptance tests as executable specifications written in a custom in-code DSL (no Gherkin) - four layers (spec, DSL, driver, system), naming, assertions, data isolation, channel swapping, and how nWave mandates map onto DSL mode
user-invocable: false
disable-model-invocation: true
---

# ATDD with a Custom DSL (DSL Mode)

Acceptance tests written as ordinary test code in the project's language, reading like a specification through a domain-specific language. No `.feature` files, no step-definition glue. The approach follows Dave Farley's four-layer acceptance test architecture and Dan North's behaviour-driven naming.

Language-agnostic rules; examples in Kotlin. Translate idioms to the target language, keep the layer contracts.

## When DSL Mode Applies

The acceptance designer decides the spec mode in Phase 0 and logs `[spec-mode] dsl|gherkin`:

1. The project CLAUDE.md declares it (`Acceptance tests: DSL` or `Acceptance tests: Gherkin`) -- this wins.
2. Otherwise, existing acceptance tests decide: `.feature` files present -> `gherkin`; acceptance `specs/` + `dsl/` + `drivers/` structure present -> `dsl`.
3. Greenfield with neither -> ask the user (`CLARIFICATION_NEEDED` in subagent mode), then offer to record the answer in CLAUDE.md.

## The Four Layers

```
Spec      what the system must do          business sentences, Given/When/Then by layout
  |
DSL       the domain vocabulary            builders, actions, assertions in domain terms
  |
Driver    how to talk to one channel       translation to the system's API / UI / protocol
  |
System    the application under test       driving facade(s) of the bounded contexts
```

Each layer may depend only on the layer directly below it. Specs never see drivers or production types. Drivers never decide business outcomes.

### Layout

```
acceptance/
  specs/            AccountsSpec (abstract) + InMemoryAccountsSpec (concrete per channel)
  dsl/              AccountsDsl, GameLibraryDsl, GamesDsl ...
  dsl/domain/       Account, Guest, GameLibrary ... (test-side domain objects)
  drivers/<context>/AccountsDriver (interface) + InMemoryAccountsDriver, UiAccountsDriver ...
```

Follow the project's existing structure if it differs.

## Layer 1 -- Specs

The spec is the living documentation. A product owner reads the test names and bodies and understands the behaviour without knowing the code.

- **Abstract spec per capability**, declaring the DSLs it needs as abstract properties. It contains every test for that capability and nothing channel-specific.
- **Concrete spec per channel** (`InMemoryAccountsSpec`, `UiAccountsSpec`) only wires the DSLs to drivers and boots the system. Display name: `"<Capability> (<channel>)"`.
- **Test names** are business sentences in present tense and active voice, stating the rule. No `should` prefix (that is for unit tests), no technical words.
  - `unregistered users can register a new account`
  - `an account cannot create two profiles with the same name`
  - not: `register returns success`, `test duplicate profile`, `should save account to repository`
- **Body** has three blocks separated by a blank line: context, action, outcome. No comments (`// given`), no mixing of the blocks.
- **One behaviour per test.** A test about library creation does not also check account registration.
- **No control flow** (`if`, loops, `try`) and no computation in spec bodies.
- **Only the data that matters to the rule is written in the spec.** Everything incidental comes from builders.

```kotlin
abstract class ProfileSpec
{
    protected abstract val accounts: AccountsDsl
    protected abstract val profiles: ProfilesDsl

    @Test
    fun `an account cannot create two profiles with the same name`() = runTest {
        val account = accounts.aRegisteredAccount()
        val existing = profiles.createFor(account)

        val attempt = profiles.tryCreateFor(account, name = existing.name)

        attempt.shouldBeRejectedAsDuplicate()
    }
}

@DisplayName("Profiles (in-memory)")
class InMemoryProfileSpec : ProfileSpec()
{
    private val system = bootstrapInMemoryGameCurator()

    override val accounts = AccountsDsl(driver = InMemoryAccountsDriver(accounts = system.accounts))
    override val profiles = ProfilesDsl(driver = InMemoryProfilesDriver(profiles = system.profiles))
}
```

## Layer 2 -- DSL

The DSL is the ubiquitous language of the tests. It is the only API specs use.

- **One DSL class per bounded context or capability** (`AccountsDsl`, `GameLibraryDsl`). A DSL may use other DSLs to build preconditions (`ProfilesDsl` asks `GameLibraryDsl` for a library).
- **Builders** create incidental context with unique, random defaults: `aNewGuest()`, `aGame()`, `anEmptyLibrary()`. Named, nullable overrides for the values a test cares about: `aGame(title = "Doom")`.
- **Precondition shortcuts** compose actions instead of copying setup: `aRegisteredAccount() = register(aNewGuest())`. This is how a later scenario reuses an earlier scenario's context (chained narrative).
- **Actions** use domain verbs and return DSL domain objects: `register(guest): Account`, `createFor(account): Profile`.
- **Attempts** for behaviour that may be rejected: `tryCreateFor(...)` returns an attempt object; the spec asserts on it in the outcome block. This keeps action and outcome separate. Avoid combined "act and assert" methods like `shouldFailToCreateDuplicate(...)`.
- **No business logic.** The DSL never reimplements a rule of the system (no duplicate checks, no price calculation). It delegates to the driver.
- **Every parameter is honoured.** A DSL method that accepts an argument and ignores it (`createFor(account)` that does not associate the account) lies to the reader. Either pass it through or remove it.
- **Speak in DSL objects, not raw ids.** `profile.assign(library)`, not `profile.assign(library.id)`.

```kotlin
class AccountsDsl(
    private val driver: AccountsDriver,
)
{
    fun aNewGuest(): Guest
    {
        val random = Uuid.random()

        return Guest(
            email = "guest-$random@example.com",
            password = "Password-$random",
            username = "guest-$random",
        )
    }

    suspend fun register(guest: Guest): Account
    {
        return driver.register(guest)
    }

    suspend fun aRegisteredAccount(): Account
    {
        return register(aNewGuest())
    }
}
```

## DSL Domain Objects and Assertions

Test-side representations of what the user deals with: `Account`, `GameLibrary`, `Profile`. They are **not** the production domain classes; they hold only what the tests need (usually an id, the values a test refers to, and a driver handle).

- Pure values (input data such as `Guest`) are plain data classes.
- Handles to things in the system carry the driver and expose **actions** (`library.add(game)`) and **assertions** (`library.shouldContain(game)`).
- **Assertions read as domain statements**: `account.shouldBeRegistered()`, `library.shouldBeEmpty()`, `decks.shouldShowExactly(first, second)`. Never `assertTrue(library.contains(game))` in a spec.
- **Every assertion has a message** stating what was expected, in domain terms, and what actually happened.
- When a rule says "and nothing else changed", assert it explicitly: `shouldContainExactly(...)`, `shouldShowExactly(...)`, not a loose `shouldContain`.

```kotlin
class GameLibrary(
    val id: String,
    private val driver: GamesLibraryDriver,
)
{
    suspend fun add(game: Game)
    {
        driver.add(library = this, game = game)
    }

    suspend fun shouldContain(game: Game)
    {
        assertTrue(
            driver.contains(library = this, game = game),
            "Expected game library `$id` to contain `${game.title}`, but it was missing",
        )
    }
}
```

## Layer 3 -- Drivers

A driver knows how to talk to one channel. It is the only test code that knows production types, commands, endpoints or UI selectors.

- **Driver interface per context**, expressed in DSL types (`fun register(guest: Guest): Account`). The interface is channel-neutral.
- **One implementation per channel**: `InMemory…Driver` (in-process, calls the driving facade), `Ui…Driver` (Compose / browser), `Http…Driver`, `Cli…Driver`. The same abstract spec runs against each.
- **Drivers enter through the driving port only** -- the bounded context's facade, the UI, the public API. Never repositories, services or domain classes directly.
- **Translate, do not judge.** The driver maps DSL data to commands and production results back to DSL objects or attempt results. It never decides whether a business rule held; that is the DSL assertion's job.
- **Fail loudly on impossible states** with context (`error("Account for `$email` was not found after registration (outcome: $outcome)")`), so a broken system produces a readable failure rather than a null pointer.
- Drivers may read back through the facade to resolve ids after an action (register, then look up by email).

```kotlin
class InMemoryAccountsDriver(
    private val accounts: Accounts,
) : AccountsDriver
{
    override suspend fun register(guest: Guest): Account
    {
        val outcome = accounts.register(
            command = CreateNewAccountCommand(
                email = guest.email,
                password = guest.password,
                username = guest.username,
            ),
        )
        val stored = accounts.findByEmail(guest.email)
            ?: error("Account for `${guest.email}` was not found after registration (outcome: $outcome)")

        return Account(
            id = stored.id,
            email = stored.email,
            driver = this,
        )
    }
}
```

## Layer 4 -- The System

The system is booted through its **production composition root** (the same `bootstrap…()` the application uses), with driven adapters chosen by the project's ATDD infrastructure policy: in-memory for the in-memory channel, real ones for an integration channel. Specs never construct services or repositories by hand.

## Isolation and Parallelism

- Every concrete spec instance boots its own system. No shared mutable state between tests.
- Every builder generates unique data (random UUID suffixes), so tests never collide even when sharing a real database.
- Acceptance tests run in parallel by default. A test that cannot run in parallel is a design smell in the DSL or the system.
- Never depend on test execution order.

## Asynchronous Systems

If the system's driving port is asynchronous (Kotlin `suspend`), the driver interface, DSL and DSL objects are asynchronous too, and each spec test runs inside the test coroutine runner (`= runTest { ... }`). Specs do not deal with threads, dispatchers or waiting; drivers for eventually-consistent channels (UI, messaging) poll with a timeout internally and fail with a domain-worded message.

## Tags, Skips and RED Scaffolds

- Tags through the test framework's tag mechanism (JUnit `@Tag`): `walking-skeleton`, `kpi`, `infrastructure-failure`, `real-io`.
- One test enabled at a time. Pending tests carry the framework's skip marker with a reason (`@Disabled("pending")`).
- RED scaffolds (production facade methods that do not exist yet) follow the `nw-distill` Mandate 7 rule: compile, carry the scaffold marker, and throw an assertion error (`throw AssertionError("Not yet implemented -- RED scaffold")` with `// SCAFFOLD: true`).

## How nWave Mandates Map onto DSL Mode

DSL mode keeps every mandate about **what** is tested and replaces the Gherkin-specific mechanics.

| nWave rule | In DSL mode |
|---|---|
| Mandate 1 -- hexagonal boundary | Applies. Drivers enter through driving ports only |
| Mandate 2 -- business language, three abstraction layers | Applies. Spec = business, DSL = domain vocabulary, driver = technical |
| Mandate 3 -- journey completeness, walking skeletons | Applies. Walking skeletons tagged `walking-skeleton` |
| Mandate 4 -- pure function extraction before fixtures | Applies |
| Mandate 7 -- RED-ready scaffolding | Applies (see above) |
| Pillar 1 -- domain language | Applies to test names, spec bodies, DSL method names |
| Pillar 2 -- chained narrative | Realised through DSL precondition shortcuts (`aRegisteredAccount()` reuses `register`) instead of shared step methods |
| Pillar 3 -- app as in production | Applies. Concrete specs boot the production composition root |
| Mandate 8 -- `assert_state_delta` universe | Replaced by explicit DSL assertions. "Nothing else changed" is asserted with exact-match assertions (`shouldContainExactly`) where the rule demands it. No state-delta port is bootstrapped |
| Mandates 9-11 -- property-based acceptance, Tier B state machines | Not used. Acceptance tests are example-based; uniqueness comes from random builder data. Property-based tests belong to unit tests of pure domain rules |
| `@contract-shape` tag | Not required. Preservation contracts are expressed as exact-match DSL assertions |
| Mandate 12 -- domain types module, step-body AST check, step-reuse ratio | Replaced by: DSL domain objects in `dsl/domain/`; spec bodies free of control flow and of driver/production imports; DSL methods delegate to drivers without business logic. No reuse ratio |
| `.feature` files as scenario SSOT | The abstract spec classes are the SSOT. `feature-delta.md` lists spec class + test names |
| Phase 2.5 completeness audit, error-path ≥40%, Fixture Theater rule, one-at-a-time | Apply unchanged |

## Review Checklist

1. Every test name is a business sentence a product owner understands; no `should`, no technical terms.
2. Context / action / outcome are separate blocks; no comments; no control flow.
3. One behaviour per test.
4. Abstract specs import only DSLs and DSL domain objects -- no drivers, no production types.
5. Incidental data comes from builders; only rule-relevant values are written in the spec.
6. Assertions read as domain statements and every one has a descriptive message.
7. Rejections are asserted on attempt objects, not inside combined act-and-assert methods.
8. Every DSL parameter is used; DSL methods take DSL objects, not raw ids.
9. Drivers go through driving ports only and contain no business decisions.
10. Concrete specs boot the production composition root.
11. Tests are isolated (fresh system, unique data) and safe to run in parallel.

## Anti-Patterns

| Anti-pattern | Instead |
|---|---|
| Spec calls a driver or production class directly | Go through the DSL |
| `assertTrue(driver.contains(...))` in a spec | `library.shouldContain(game)` |
| DSL method ignores one of its parameters | Pass it through or remove it |
| `shouldFailToX(...)` performing the action and the assertion | `tryX(...)` in the action block, `attempt.shouldBeRejectedAsY()` in the outcome block |
| Hard-coded shared test data (`"test@example.com"`) | Builder with unique random default |
| DSL reimplementing a business rule to compute expected values | Assert observable outcomes through the driver |
| Driver deciding pass/fail of a business rule | Driver translates; DSL asserts |
| Driver reaching into repositories to set up state | Set up state through the driving port, using DSL precondition shortcuts |
| Comments labelling given/when/then | Blank-line separated blocks |
| One test per DSL method ("test register", "test findByEmail") | One test per business rule |

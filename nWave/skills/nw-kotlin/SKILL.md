---
name: nw-kotlin
description: Kotlin house style for both crafters - functional services with object-oriented structure, suspend-first coroutines, sealed per-operation outcomes, kotlin-logging, and pure JUnit Jupiter testing
user-invocable: false
disable-model-invocation: true
---

# Kotlin -- House Style

Load for any Kotlin project, regardless of paradigm (functional or object-oriented crafter). This skill describes the default. If the user or the project's CLAUDE.md explicitly says otherwise, the explicit instruction wins. Never "upgrade" a project away from these defaults on your own initiative, and never silently deviate from them either; ask.

Cross-references: [hexagonal-testing](../nw-hexagonal-testing/SKILL.md) | [property-based-testing](../nw-property-based-testing/SKILL.md) | [atdd-dsl](../nw-atdd-dsl/SKILL.md)

## Paradigm: Functional in the Small, Object-Oriented in the Large

Kotlin is multi-paradigm. Use each paradigm where it is strongest:

| Layer | Shape | Paradigm |
|---|---|---|
| Domain (entities, value objects, rules) | Immutable `data class`, sealed hierarchies, invariants checked at construction | Functional values |
| Services (use cases) | Top-level `suspend fun`, command + ports passed as named parameters, returns `ServiceResult` | Functional |
| Driven ports | `interface` in business language | Object-oriented |
| Driving port (per bounded context) | One facade `interface` listing the context's use cases | Object-oriented |
| Adapters | `class` with constructor injection | Object-oriented |
| Composition root | Plain `bootstrap…()` function, manual wiring | Neither -- just wiring |

Do NOT model ports as function type aliases, and do NOT turn services into classes with injected fields. Services stay functions; structure stays classes and interfaces.

## Project Layout (Hexagonal)

Follow the layout the project already has. When starting fresh:

```
<context>/
  adapters/driving/     UI, CLI, HTTP handlers (primary adapters)
  adapters/driven/      repositories, clocks, identity, external APIs (secondary adapters)
  app/domain/           entities, value objects, aggregates
  app/ports/            driven port interfaces + the driving facade interface
  app/service/          use-case functions, commands, outcomes
  startup/              composition root (bootstrap functions)
```

Dependencies flow inward: adapters -> ports -> domain. `app/domain` imports nothing from `app/service`, `app/ports` or `adapters`.

## Domain

- `data class` with `val` properties only. State changes return new values (`copy`).
- Invariants are checked in `init`. A violated invariant **throws** (the project's `AssertionException` / `DomainObject` helpers when present, otherwise `require`). Constructors never return `ServiceResult`.
- Rule: **a constructor guards invariants; a service decides which failures are expected outcomes.** Services catch construction failures and map them to a named outcome.
- Choice types are `sealed interface` hierarchies; handle them with exhaustive `when`, never an `else` branch on a sealed type.
- Never `suspend`, never `Flow`, never logging, never IO. Domain code is synchronous and pure.
- Hide secrets from `toString` (passwords, tokens).

```kotlin
data class Account(
    val id: String,
    val email: String,
    val password: String,
) : DomainObject()
{
    init
    {
        this::email.mustNotBeBlank()
    }

    override fun toString() = super.toString()
}
```

## Ports

Driven ports are interfaces named in business language. Every operation is `suspend`, except `observe…` functions, which return `Flow`.

```kotlin
interface AccountsRepository
{
    suspend fun store(account: Account)
    suspend fun findByEmail(email: String): Account?
}
```

### Driving facade (one per bounded context)

Each bounded context behaves like a small application. It exposes one facade interface listing its use cases. Its implementation is a mini bootstrap: it holds the driven ports and delegates to the service functions. Acceptance-test drivers and UI adapters talk **only** to this interface.

```kotlin
interface Accounts
{
    suspend fun register(command: CreateNewAccountCommand): ServiceResult<CreateAccountOutcomes, Unit>
    suspend fun findByEmail(email: String): Account?
}

class AccountsApp(
    private val accountsRepository: AccountsRepository,
    private val identityMint: IdentityMint,
) : Accounts
{
    override suspend fun register(command: CreateNewAccountCommand): ServiceResult<CreateAccountOutcomes, Unit>
    {
        return createNewAccount(
            command = command,
            accountsRepository = accountsRepository,
            identityMint = identityMint,
        )
    }

    override suspend fun findByEmail(email: String): Account?
    {
        return accountsRepository.findByEmail(email)
    }
}
```

Name the implementation after what it is, not after the adapters it happens to be wired with (`AccountsApp`, not `InMemoryAccounts`).

## Services and Error Handling

A service is a top-level `suspend fun` taking a command plus the ports it needs as named parameters. It returns `ServiceResult<Outcome, Value>` (sealed `Success` / `Failure`, from the project's shared protocol module). Do not introduce Arrow, and do not use `kotlin.Result` in services.

Rules:

1. **Every step of a use case that can fail gets a named outcome in business language.** Uniqueness check, storing, lookup -- these are business steps even though a port performs them, and they exist even without infrastructure. Example: `AccountAlreadyExists`, `DuplicateLookupFailed`, `StoreAccountFailed`.
2. Outcomes form one `sealed interface <Operation>Outcomes` per operation. Each error carries a stable id, a message, a business payload, and an opaque `cause: Throwable?`.
3. **Callers never branch on the type of `cause`.** It exists for logs and diagnostics only.
4. **Retryability is a flag, not a type switch.** Driven adapters wrap technical failures that may succeed on retry (timeouts, HTTP 503, locked database, dropped connection) in `TransientException(cause)`. The outcome exposes `isRetryable`:

   ```kotlin
   sealed class Error(...) : CreateAccountOutcomes
   {
       abstract val cause: Throwable?
       val isRetryable: Boolean get() = cause is TransientException
   }
   ```

   Only adapters throw `TransientException`. Domain and services never do.
5. Compose steps with early return. Use the shared helpers (`runServiceCatching`, `checkForDuplicate`, `storeOrFail`, `getOrElse`, `onFailure`, `mapFailure`) rather than re-deriving try/catch per service. They are `inline`, so suspend calls work inside their lambdas.

```kotlin
suspend fun createNewAccount(
    command: CreateNewAccountCommand,
    accountsRepository: AccountsRepository,
    identityMint: IdentityMint,
): ServiceResult<CreateAccountOutcomes, Unit>
{
    val account = makeAccountFromCommand(
        command = command,
        identityMint = identityMint,
    ).getOrElse { return ServiceResult.Failure(it) }
    checkForDuplicate(
        lookup = { accountsRepository.findByEmail(command.email) },
        onLookupFailure = { CreateAccountOutcomes.DuplicateLookupFailed(payloadOf(command), cause = it) },
        onDuplicate = { CreateAccountOutcomes.AccountAlreadyExists(payloadOf(command)) },
    ).onFailure { return ServiceResult.Failure(it) }
    storeOrFail(
        store = { accountsRepository.store(account) },
        onFailure = { CreateAccountOutcomes.StoreAccountFailed(payloadOf(command), cause = it) },
    ).onFailure { return ServiceResult.Failure(it) }
    return ServiceResult.Success(Unit)
}
```

Services do not log, and they do not choose threads. They return outcomes; the driving side decides what to log and show.

## Coroutines -- Always Suspend

Ports, services and driving facades are `suspend` by default. Do not write a blocking variant unless the user explicitly asks for one.

1. **Domain is never `suspend`.** Coroutines stop at the service layer.
2. **Adapters are main-safe.** An adapter wrapping a blocking library switches context itself, using an injected dispatcher so tests can replace it:

   ```kotlin
   class SqlAccountsRepository(
       private val database: Database,
       private val io: CoroutineDispatcher,
   ) : AccountsRepository
   {
       override suspend fun findByEmail(email: String): Account?
       {
           return withContext(io) {
               database.accountQueries.findByEmail(email).executeAsOneOrNull()?.toDomain()
           }
       }
   }
   ```

3. Services and domain never choose a dispatcher.
4. **`runBlocking` is forbidden in production code.** Suspend-only libraries (Ktor) are called directly from `suspend` adapter functions.
5. **Every catch-all rethrows `CancellationException`.** Swallowing it turns a cancelled operation into a fake failure and breaks structured concurrency. This includes the project's `runServiceCatching` and Kotlin's own `runCatching` (avoid the latter in suspend code).

   ```kotlin
   inline fun <V> runServiceCatching(block: () -> V): ServiceResult<Throwable, V>
   {
       return try
       {
           ServiceResult.Success(block())
       }
       catch (e: CancellationException)
       {
           throw e
       }
       catch (e: Exception)
       {
           ServiceResult.Failure(e)
       }
   }
   ```

   Catch `Exception`, not `Throwable`; `Error`s (out of memory, stack overflow) must propagate.
6. **One layer owns retrying.** An adapter may retry briefly inside itself (with `delay`, never `Thread.sleep`). Once it gives up, it throws `TransientException`, and the caller decides what happens next. Never stack retry loops across layers.
7. Concurrency inside a use case uses structured primitives (`coroutineScope { async { } }`), never `GlobalScope`.

### Observable queries -- `Flow`

`Flow` is treated as part of the language, like `suspend`, but kept narrow:

- The domain never sees `Flow`.
- A `Flow` exists only where something is **observed over time**: an `observe…` function on a driven port or driving facade. Everything else is a `suspend fun` returning a value.
- The `observe` prefix carries the meaning ("a stream of snapshots"). Callers depend on that meaning, not on how the stream is produced.
- Services only pass streams through or `map` them into domain terms. They never collect or buffer them.
- Do not wrap `Flow` in a custom reactive abstraction.

```kotlin
interface OwnedGameRepository
{
    suspend fun store(libraryId: String, game: OwnedGame)
    fun observeGamesIn(libraryId: String): Flow<List<OwnedGame>>
}
```

## Composition Root

Wiring happens in plain `bootstrap…()` functions under `startup/`. No DI container unless the project already uses one. The composition root is the only place that knows concrete adapter classes.

```kotlin
fun bootstrapInMemoryGameCurator(): GameCurator
{
    return GameCuratorApp(
        accounts = AccountsApp(
            accountsRepository = InMemoryAccountsRepository(),
            identityMint = UuidIdentityMint(),
        ),
    )
}
```

## Logging -- kotlin-logging

Use `io.github.oshai:kotlin-logging`. Never call SLF4J's `LoggerFactory` directly, and never use `println` for diagnostics.

```kotlin
private val logger = KotlinLogging.logger {}

class SteamApiClient(...)
{
    suspend fun ownedGames(steamId: String): List<SteamOwnedGame>
    {
        logger.info { "Fetching owned games for $steamId" }
        ...
        logger.error(exception) { "Fetching owned games failed for $steamId" }
    }
}
```

- Declare the logger as a top-level `private val` in the file.
- Always use the lambda form (`logger.debug { "..." }`) so messages are only built when the level is enabled.
- Pass exceptions as the first argument, not inside the message string.
- Log in adapters and the composition root. The domain never logs; services return outcomes instead of logging.
- Never log secrets (API keys, passwords, tokens).

## Code Style

- **Allman braces**: opening brace of classes, functions, `if`, `when`, `try`, `catch` on its own line. Lambdas passed as the last argument keep the brace on the same line (`map { ... }`).
- Trailing commas in multi-line parameter and argument lists.
- Named arguments for any call with more than one argument, and always for constructors.
- Public functions declare return types explicitly and use block bodies with `return`. Expression bodies only for trivial one-liners.
- Early return and guard clauses instead of `if`/`else` chains. Avoid nesting.
- Small, focused functions named in domain language.
- Format with the project's formatter configuration when one exists; it wins over this list.

## Testing -- Pure JUnit Jupiter

- **JUnit Jupiter only**, versioned through the JUnit BOM (`org.junit:junit-bom`, latest stable). No Kotest runner, no Spek, no kotlin.test assertions.
- Assertions: `org.junit.jupiter.api.Assertions` (`assertEquals`, `assertTrue`, `assertThrows<T>`), **always with a message** that states what was expected, what happened, and why it matters.
- Test classes carry `@DisplayName` with a noun ("Account"). Unit test names start with `should`.
- Arrange / act / assert are separated by blank lines. No `// given` comments.
- Suspend code is tested with `kotlinx-coroutines-test`: `` @Test fun `should ...`() = runTest { ... } ``. Inject `StandardTestDispatcher` / `UnconfinedTestDispatcher` where an adapter takes a dispatcher. `delay` runs in virtual time.
- Test data via builder functions with nullable overrides and random defaults, kept in the test `support` package:

  ```kotlin
  fun makeRandomAccount(
      id: String? = null,
      email: String? = null,
  ): Account
  {
      val random = Uuid.random()

      return Account(
          id = id ?: "${Uuid.generateV7()}",
          email = email ?: "user-$random@example.com",
      )
  }
  ```

- Unique random data per test so tests run in parallel without interference.
- Test doubles: in-memory implementations of driven ports. A mocking library only when the user has agreed to one.
- Acceptance tests use the project's acceptance DSL (specs -> DSL -> drivers -> driving facade, see `nw-atdd-dsl`); they are authored by the acceptance designer, not the crafter.

### Property-based tests -- `kotest-property` inside JUnit

Use property tests for **pure domain rules** with an obvious invariant: normalization and deduplication (signatures), parsing and mapping of external data, serialization round-trips, ordering and filtering. Never for acceptance tests or simple store-and-read flows.

Use `io.kotest:kotest-property` as a library inside a normal Jupiter test. It is multiplatform, so it works from `commonTest`. Do not use jqwik (separate test engine, JVM only, maintenance mode) unless the user asks.

```kotlin
@DisplayName("GameSignature")
class GameSignatureTest
{
    @Test
    fun `should treat titles differing only by surrounding whitespace as the same game`() = runTest {
        checkAll(Arb.string(minSize = 1)) { title ->
            assertEquals(
                GameSignature(title = title, developer = "dev", releaseYear = 2000),
                GameSignature(title = " $title ", developer = "dev", releaseYear = 2000),
                "Expected signatures for `$title` and ` $title ` to be equal, but they differ",
            )
        }
    }
}
```

When a property fails, the seed is printed. Reproduce with `checkAll(PropTestConfig(seed = <seed>), ...)` and turn the shrunk counterexample into a named example test.

## Dependencies

Prefer the standard library and small in-house helpers over new libraries. Do not add a dependency without discussing its purpose and alternatives with the user. Approved defaults: `kotlinx-coroutines`, `kotlinx-datetime`, `kotlinx-serialization`, `kotlin-logging`, JUnit Jupiter, `kotlinx-coroutines-test`, `kotest-property` (test only).

## Anti-Patterns -- Reject on Sight

| Anti-pattern | Instead |
|---|---|
| `runBlocking` in production code | `suspend` all the way to the driving adapter |
| `catch (e: Throwable)` / `runCatching` around suspend calls | Catch `Exception`, rethrow `CancellationException` |
| Callers branching on `cause is SomeTechException` | A named outcome, or the `isRetryable` flag |
| Service implemented as a class with injected fields | Top-level `suspend fun` with ports as parameters |
| Ports as function type aliases | `interface` in business language |
| `suspend` or `Flow` in domain types | Synchronous, pure domain |
| Arrow `Either` / Raise DSL introduced into a project without it | `ServiceResult` + sealed outcomes |
| `LoggerFactory.getLogger(...)`, `println` | `KotlinLogging.logger {}` |
| Eager log messages (`logger.info("..." + x)`) | Lambda form `logger.info { "..." }` |
| Hardcoded secrets or personal ids as default parameters | Configuration injected by the composition root |
| Assertions without messages | Message stating expected, actual, and why |
| Kotest specs, MockK, Spek | JUnit Jupiter + in-memory port implementations |

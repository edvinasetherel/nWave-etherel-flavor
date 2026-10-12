---
name: nw-naming
description: Naming discipline - types name things, functions name actions, role suffixes, banned filler words, vocabulary reuse, self-check before handoff
user-invocable: false
disable-model-invocation: true
---

# Naming

A name is a design decision. If you can't name something precisely, the design is usually wrong (see `nw-hybrid-paradigm`), not the vocabulary.

Cross-references: [hybrid-paradigm](../nw-hybrid-paradigm/SKILL.md) | [kotlin](../nw-kotlin/SKILL.md) | [fp-usable-design](../nw-fp-usable-design/SKILL.md) (FP naming specifics)

## Why names go wrong

The most obvious name is the task's own verb turned into a noun. Asked to "pull records", you write `RecordPull`. Asked to "look things up", you write `Lookup`. These names describe **what you were doing when you wrote the code**, not **what the code is**. Resist the first name that comes to mind. Generate two or three candidates, then pick by the rules below. When you replace a first-draft name, mention the rejected candidates in the handoff.

## Rule 1 -- Types name things, functions name actions

- **A type** (class, interface, record, module object) is a **noun phrase for something that exists**: a domain concept (`OwnedGame`, `GameSignature`), an outside capability (`GameCatalog`, `Clock`) or a role (`StoredRecordsRepository`).
- **A function** is a **verb phrase for what happens**: `pullSteamLibrary`, `matchSteamApps`, `storeRecords`.
- **Test:** can you say what one instance *is* without saying what it *does*? If the best noun you can find for a type is an action (`Pull`, `Lookup`, `Sync`, `Import`, `Fetch`), and the type implements no port, it should be a function.

## Rule 2 -- Role suffixes must mean their role

The suffix names the **port's role**. An adapter keeps the port's full name and adds a **technology prefix**: port `StoredRecordsRepository`, adapters `SqliteStoredRecordsRepository` and `InMemoryStoredRecordsRepository`.

| Suffix | Means | Example |
|---|---|---|
| `…Repository` | A port that stores and finds domain things or records | `StoredRecordsRepository`, `AccountsRepository` |
| `…App` | Implementation of a bounded context's driving facade | `AccountsApp` |
| `…Command` / `…Outcomes` | The input and the outcomes of one use case | `CreateNewAccountCommand`, `CreateAccountOutcomes` |
| `bootstrap…` (function prefix) | A composition root | `bootstrapIgdbCli` |

Ports that give read access to outside knowledge take a domain noun, not a suffix: `GameCatalog`, `Clock`, `IdentityMint`.

**One exception:** `…Client` names a thin adapter over one external API, in that API's own terms (`IgdbClient`, `SteamApiClient`). It is not technology + port. Business rules never go in a `…Client`; an adapter such as `IgdbGameCatalog` wraps it to translate into our terms.

## Rule 3 -- Banned and suspicious words

These words carry no meaning, or hide an action dressed as a thing. In **type names**, replace them unless the word is the established domain term in this codebase or business (a game engine is an `Engine`). When you keep one, say so in the handoff.

| Word | Problem | Instead |
|---|---|---|
| `Manager`, `Helper`, `Util(s)`, `Processor`, `Service` (as a class in a hybrid project) | Says "something does stuff" | Name the concept, or turn it into functions |
| `Pull`, `Lookup`, `Sync`, `Fetch(er)`, `Import(er)`, `Loader` | An action, not a thing | A function, or the port/adapter it really is |
| `Handler`, `Runner`, `Executor`, `Engine`, `Controller` | Usually filler. Legitimate when a framework or the domain defines the role (an HTTP handler, a test runner, a coroutine executor, a game engine) | The concept, unless that framework or domain role applies |
| `Data`, `Info`, `Item`, `Object`, `Thing`, `Stuff`, `Record` alone | Generic; true of everything | The domain noun (`OwnedGame`, `IgdbGameRecord`) |
| `Ids`, `Values`, `List`, `Map` as a whole type name | Names the data structure, not the meaning | The concept the collection stands for (`StoredRecords`, `UnmatchedGames`). Query functions may return them: `storedIds(endpoint)` is fine |
| `Impl`, `Default…`, `Base…`, `My…`, a leading `New…` | Says nothing about how it differs | The technology or the variant (`Sqlite…`, `InMemory…`) |
| Abbreviations (`mgr`, `cfg`, `repo`, `ctx`, `res`, `tmp`) | Saves keystrokes, costs readers | Full words. Standard ones stay: `id`, `url`, `uri`, `db`, `io`, `http`, `json`, `sql`, `api` |

## Rule 4 -- Reuse the vocabulary that exists

Before naming anything new:

1. **Search the codebase** for the concept: ports in `ports/`, shared modules, and the acceptance DSL. If `Clock`, `IdentityMint`, `OwnedGame` or `GameLibrary` already exist, use them. Don't invent synonyms.
2. **Use the ubiquitous language** of the ticket, the specs and the domain docs. If the ticket says "owned game", the code says `OwnedGame`, not `SteamTitle`.
3. **Don't overload** an existing name with a different meaning. If two concepts collide, qualify the new one (`IgdbGameRecord` vs the domain `Game`) and mention it in the handoff.
4. **Keep sibling consistency.** A second adapter of a port follows the first one's pattern (`InMemoryAccountsRepository` ↔ `SqlAccountsRepository`).

## Rule 5 -- Function names

- **Commands** change something: a verb plus its object (`storeRecords`, `registerAccount`).
- **Queries** return something: name the result (`storedIds`, `ownedGames`, `referencedIds`). A `get` prefix on a query that computes adds nothing.
- **Predicates** read as a question (`isStored`, `hasMatch`, `canRetry`).
- **Conversions** say the target (`toDomain`, `asJson`). Use `parse…` / `render…` at text boundaries.
- **One action per name.** `fetchAndStore` means two responsibilities: split it.
- **Don't encode the implementation** (`fetchFromSqlIntoMap`) or **the type** (`gameList`, `nameString`). Name the intent and the meaning (`games`, `title`).
- **Name by abstraction level.** A use case function reads like the ticket (`pullSteamLibrary`). The private helpers under it name the steps (`matchOwnedGames`, `followReferences`).

## Rule 6 -- Files and packages

- **One main concept per file**, and the file is named after it. Never `Utils.kt`, `Helpers.py` or `Common.ts`.
- **Packages and folders** are named after the bounded context or the hexagonal layer, never after a pattern (`managers/`, `helpers/`).

## Rule 7 -- Tests and DSLs

- **Unit test names** follow the project convention and state behaviour from the client's point of view (`should …` in Kotlin projects, see `nw-kotlin`).
- **Acceptance DSL names** read as the business would say them (`library.shouldContain(game)`, `steam.ownsGames(3)`), never as mechanics (`db.insertRow`).
- **Test support** (builders, drivers) follows the same rules: `makeRandomAccount`, `SteamLibraryDriver`. Never `TestHelper` or `Utils`.

## Self-Check Before Handoff

For every new type and every new public function:

1. Can I say what one instance **is** in one sentence without saying what it does? (Rule 1; for the shape, `nw-hybrid-paradigm`.)
2. Is a word from Rule 3 in a type name? Is it an established domain or framework term, or filler?
3. Does this concept already exist in the codebase under another name (Rule 4)?
4. Would a domain expert reading the ticket recognise the name?
5. Does the suffix match the role, and does each adapter carry technology + port name (Rule 2)?

Fix what fails. **List the names you introduced in the handoff**, so the user can comment on them.

## Worked Example

| First-draft name | Problem | Better |
|---|---|---|
| `IgdbPull` (class) | An action as a type; a procedure in disguise | `pullSteamLibrary(...)` service function |
| `IgdbLookup` (class) | An action as a type; really our view of IGDB | Port `GameCatalog` + adapter `IgdbGameCatalog` |
| `StoredIds` (class) | Names a data structure; the concept is the stored records | Query on `StoredRecordsRepository` (`storedIds(endpoint)`) |
| `SeedStore` | Vague: what is stored? | `SqliteStoredRecordsRepository` |
| `References` (object) | Too generic for a table of IGDB reference fields | `IgdbReferenceTable` / `referencedIds(...)` |
| `fetchAndStore` | Two actions: two responsibilities | `fetchRecords` + `records.store(...)` |

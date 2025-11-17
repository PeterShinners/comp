
## Privacy System

Comp provides two privacy mechanisms that work across the entire language: module-private definitions and private data attachments. These are core syntax features (not tied to any one construct) and apply uniformly to functions, shapes, tags, handles, and structures.

### Private Definitions (trailing &)

Add a trailing `&` to a definition name to mark it module-private. Private definitions are only visible to code in the same module.

- Applies to: functions (`!func |name&`), shapes (`!shape ~Name&`), tags (`!tag #name&`), handles (`!handle @name&`)
- Referencing rule: Within the same module, reference the name without `&` (e.g., `|helper` calls `!func |helper&`). Other modules cannot reference it at all.
- Purpose: Keep implementation details internal while exposing a clean public API.

```comp
; Private function, only usable inside this module
!func |helper& ~{data} = { [$in.data |normalize |validate] }

; Public function that can call the private helper
!func |public-api ~{data} = { [data |helper] }

; Private shape and tag
!shape ~internal-config& = { secret ~str }
!tag #status& = { #pending #active #done }

; From other modules (after !import):
; [x |public-api/mod]      ; OK
; [x |helper/mod]          ; ERROR - private
; y ~internal-config/mod   ; ERROR - private
; #status.pending/mod      ; ERROR - private
```

### Private Data Attachment (& on structures)

Each module can attach private data to any structure using `&{...}`. This creates a per-module private namespace on the structure that is only accessible within the attaching module.

- Attach: `value &{private-field=...}` or `value& = {private-field=...}`
- Access: `value&.private-field` (only within the same module)
- Behavior: Private data travels with structures through pipelines and full spreads automatically.

```comp
; Create a structure with private data inline
$user = {login="pete" email="pete@example.com"}
                &{session="abc123" id=789}

; Public fields
$user.login           ; "pete"

; Private fields (same module only)
$user&.session        ; "abc123"
$user&.id             ; 789

; Separate private data assignment
$config = {url="https://api"}
$config& = {auth-token="secret"}
```

#### Inheritance and Manual Transfer

- Pipeline operations and full spread preserve private data automatically: it “flows” with the value.
- When building a brand-new structure from selected fields, private data is not copied unless you assign it explicitly.

```comp
; Automatic preservation through pipelines and full spread
$user& = {session="abc" token="xyz"}
$result = [$user |transform |validate]
$result&.session      ; "abc"

$copy = {...$user extra="field"}
$copy&.token          ; "xyz"

; Manual transfer when selecting fields
$partial = {name=$user.login}
$partial& = $user&
$partial&.session     ; "abc"
```

#### Merging from Multiple Sources

When a new structure references multiple inputs, private data from all referenced values merges using first-reference-wins for conflicting fields. This produces predictable results without requiring coordination across modules.

```comp
$a& = {token="abc" shared="first"}
$b& = {auth="xyz" shared="second"}

$merged = {from-a=$a.value from-b=$b.value}
$merged&.token   ; "abc"   ; from $a
$merged&.auth    ; "xyz"   ; from $b
$merged&.shared  ; "first" ; $a referenced first
```

For function-body privacy mode (disabling automatic field export with `&{}`), see the privacy structures section in Functions and Blocks. That feature controls output visibility within a single function, while the mechanisms above control module-level visibility and structure-attached private state.

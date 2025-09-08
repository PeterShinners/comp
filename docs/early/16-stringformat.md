## String Formatting in Comp - Design Summary

### Core Design Decisions

**String templates use `${}` interpolation syntax**
- Templates are reusable values, not immediately evaluated
- Example: `greeting = "Hello ${name}!"` creates a template
- Invoked with data to produce formatted strings: `{name="Alice"} -> greeting`

**Three interpolation modes (matching Python's behavior)**
- **Positional**: `{"World" "Pete"} -> "Hello ${} and ${}!"` → `"Hello World and Pete!"`
- **Explicit index**: `{"A" "B" "C"} -> "${#2} ${#0} ${#1}"` → `"C A B"`
- **Named fields**: `{name="Alice" age=30} -> "${name} is ${age}"` → `"Alice is 30"`
- Can mix positional with named, but not positional with explicit indices (Python's rules)

### Formatting Philosophy

**No format specifiers in templates**
- Unlike Python's `f"{value:.2f}"`, Comp uses preprocessing pipelines
- Transform data before invoking the template:
  ```comp
  {pi=3.14159} 
    -> {pi -> :number:round(2)}
    -> "π is approximately ${pi}"
  ```

**Formatter objects for consistent formatting**
- Configure formatting rules as data:
  ```comp
  $fmt = {number.separators=#true number.digits=2 date.format="MMM DD"}
  {data formatter=$fmt} -> "Amount: ${amount} on ${date}"
  ```
- Can be set as context default: `.ctx.formatter = $fmt`

### Advanced Features

**Invoke handlers for specialized formatting**
- Attach formatters to templates: `"<h1>${title}</h1>"@html.safe`
- Context can set defaults: `.ctx.default_string_invoke = :html:safe`

**Type hints for domain-specific strings**
- `@sql"SELECT * FROM users WHERE id = ${id}"`
- Provides metadata for validation/processing when invoked

### String Operations

**No string operators in core language**
- No `+` for concatenation, no `*` for repetition
- Use functions or templates instead:
  - `{str1 str2} -> :string:concat` or `{str1 str2} -> "${}${}"`
  - `{"=" 40} -> :string:repeat`

**`:cat` as likely builtin for concatenation**
- `{"ERROR: " message} -> :cat`
- Short, follows Unix convention, handles common case

### Workflow Patterns

**Preprocessing pattern for complex formatting**
```comp
!func :fmt_financial ~{amount date~} {
    .in ..> {
        amount = {amount -> :number:commify -> :number:currency("USD")}
        date = {date -> :date:format("MMM DD")}
    }
}

records ->each :fmt_financial -> "Transaction: ${amount} on ${date}"
```

**`:nest` for logging while preserving pipeline value**
```comp
recipe -> :nest .{
    {op -> :string:prefix(4), count=values -> :length} 
    -> "Running ${op} with ${count} values"
    -> :log:info
} -> :run:recipe
```

### Key Trade-offs

- **Simplicity over brevity**: No format specifiers keeps templates simple
- **Explicit over magical**: Preprocessing makes transformations visible
- **Composable over monolithic**: Separate concerns of transformation and templating
- **Consistent over convenient**: All formatting uses same pipeline pattern

This design keeps string templates as pure interpolation while leveraging Comp's pipeline strengths for transformation and formatting.
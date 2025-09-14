## Comp Language Design Updates: Final Summary

### Module References Unified with Dot Prefix
**Previous:** Module references used type-specific prefixes that created parsing ambiguities
- `#module#tag.hierarchy` - ambiguous where module ends and tag begins
- `:module:function` - consistent but heavy
- `~module~shape` - consistent but heavy

**New:** All module references use a dot prefix followed by the type symbol
- `.module:function` - function from module
- `.module~Shape` - shape from module  
- `.module#tag#hierarchy` - tag from module (tags use `#` consistently throughout)

**Benefits:**
- Eliminates parsing ambiguity 
- Module prefix visually fades, emphasizing the actual operation/type
- Type symbol still appears first after the dot for quick recognition

Importing will use the dotted name to when defining the namespace.
`!import .claude = comp @gh/claude-comp@1.0/lib`

This also means `!describe` will not need a magic keyword when working
with modules. It can use `!describe .claude` directory.

### Tag Field Names Require Quotes
**New rule:** Tags used as struct field names must be single-quoted
```comp
a = {#status.ok}                // Unnamed field with tag value
b = {'#status.ok'="ok"}         // Field named '#status.ok' with string value
c = {'#status.ok'=#status.ok}   // Field named '#status.ok' with tag value
```

This aligns with existing rules for numeric and boolean field names, creating consistency: any field name that isn't a simple identifier requires quotes.

### Statement Locals Removed
The `^` symbol previously reserved for statement-local variables has been repurposed for context isolation, as statement locals weren't finding justification in the design.
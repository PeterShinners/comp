# Examples Directory Structure

This directory is organized to distinguish between **working examples** (that run with the current v0.1.0 implementation) and **design examples** (that demonstrate the full Comp language vision).

## 📂 Directory Layout

```
examples/
├── working/           # ✅ Examples that work NOW (v0.1.0)
│   ├── hello.comp
│   ├── greet.comp
│   └── pipeline.comp
│
└── *.comp            # 🔮 Design demonstrations (future features)
    ├── cart.comp
    ├── tree.comp
    ├── wordcount.comp
    └── ...
```

## ✅ Working Examples (v0.1.0)

Located in `working/` subdirectory. These run with the current interpreter:

```bash
comp examples/working/hello.comp
comp examples/working/greet.comp  
comp examples/working/pipeline.comp
```

**What they demonstrate:**
- Basic function definitions
- Structure literals
- Pipelines
- Builtin functions (print, upper, lower, double)
- String and numeric operations

## 🔮 Design Examples (Future)

Located in the root `examples/` directory. These showcase the full language design:

### cart.comp
Shopping cart with advanced features:
- Shape morphing (`~cart`)
- Array types (`~item[]`)
- Reduce operations (`|reduce-into`)
- Block syntax (`:{}`)
- Pattern matching

**Required features:** Blocks, morphing, loops, arrays

### tree.comp
Binary search tree implementation:
- Recursive data structures
- Pattern matching (`|match`)
- Conditional blocks (`|if`)
- Fold operations (`|fold-into`)
- Union shapes (`~tree | ~nil`)

**Required features:** Blocks, pattern matching, recursion, shape unions

### wordcount.comp
Text processing pipeline:
- I/O operations (`|stdin`, `|read-lines/io`)
- Map/reduce operations
- String splitting
- Block syntax for operations

**Required features:** I/O, blocks, map/fold/reduce

### Others
- **nushell.comp** - Shell-style pipelines
- **mayatool.comp** - 3D graphics integration
- **rio-todo.comp** - UI framework integration
- **io-uring.comp** - Async I/O patterns
- **lockless.comp** - Concurrent data structures
- **cloudflaire-ai.comp** - API integration

## 🎯 Purpose of Design Examples

These examples serve multiple purposes:

1. **Language Design Reference**: Show intended syntax and patterns
2. **Feature Targets**: Guide implementation priorities
3. **Documentation**: Demonstrate best practices for future users
4. **Testing Ground**: Validate design decisions before implementation

## 🚀 Running Examples

### Current Implementation (v0.1.0)

```bash
# These work now:
comp examples/working/hello.comp
uv run comp examples/working/greet.comp
```

### Future Implementation

```bash
# These will work when features are implemented:
comp examples/cart.comp        # (when morphing + blocks ready)
comp examples/tree.comp         # (when pattern matching ready)
comp examples/wordcount.comp    # (when I/O + loops ready)
```

## 📊 Implementation Progress

| Feature Category | Status | Examples Unlocked |
|-----------------|--------|-------------------|
| Basic literals & ops | ✅ Done | hello, greet, pipeline |
| Pipelines | ✅ Done | pipeline |
| Functions | ✅ Done | All working examples |
| Blocks `:{}` | ⏳ TODO | cart, tree, wordcount |
| Pattern matching | ⏳ TODO | tree |
| Loops (map/fold) | ⏳ TODO | wordcount, cart |
| Shape morphing | ⏳ TODO | cart, tree |
| I/O operations | ⏳ TODO | wordcount |
| Arrays `~type[]` | ⏳ TODO | cart |

## 💡 Tips for Contributors

1. **Start with working/**: Use these as templates for new features
2. **Test incrementally**: Add features one at a time
3. **Update this doc**: When a feature enables an example, move it to working/
4. **Design first**: Study the design examples to understand the vision

## 🎓 Learning Path

If you're new to Comp:

1. Read `working/hello.comp` - Simplest possible program
2. Study `working/greet.comp` - Function parameters and composition
3. Explore `working/pipeline.comp` - Data transformation
4. Browse design examples to see the language potential
5. Check `design/` directory for detailed language specification

## 📝 Creating Your Own Examples

For v0.1.0, follow this template:

```comp
!func |main ~_ = {
    // Your code here using:
    // - Structure literals: {field = value}
    // - Pipelines: [value |func1 |func2]
    // - Builtins: print, double, upper, lower
    // - Math ops: + - * / // % **
    result = "your result"
}
```

Save as `myexample.comp` and run: `comp myexample.comp`

---

**Remember**: The examples in the root directory are aspirational! They show where we're going, not where we are. For now, enjoy what works in `working/` and watch this space as more features land! 🚀

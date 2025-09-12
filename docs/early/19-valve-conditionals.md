## Valve Operators - Comprehensive Design

This completely replaces the previous descriptions of ternary operators
that used `?` and `|` characters. That was similar to C's concept of ternary,
but this is much better for Comp.

### The Valve Operator Family

All valve operators use **double characters** for visual consistency and clear control flow:

- **`-??`** Begin conditional (if)
- **`-&&`** Then action separator (and then) 
- **`-|?`** Else-if continuation (or if)
- **`-||`** Else fallback (or else)

### How Valve Groups Work

A valve group is a sequence of conditional checks that work together as a single unit in the pipeline. The group receives an input value, evaluates conditions against it, and outputs the result of whichever branch executes.

**Input Flow**: The value entering the valve group (from the left side of `-??`) is available to all conditions within that group. Each condition can access and test this input value.

**Condition Evaluation**: Conditions are evaluated in order, top to bottom. The first condition that evaluates to true has its corresponding action executed. Once a condition matches, no further conditions in that valve group are checked.

**Output Flow**: The valve group outputs whatever value its executed action produces. This output then flows to the next operation in the pipeline. If no condition matches and there's no `-||` else clause, the valve group passes through the original input value unchanged.

### Syntax Pattern

```comp
input_value -> 
    -?? condition -&& :action_if_true
    -|? another_condition -&& :action_if_this_true  
    -|| :action_if_all_false
-> receives_action_output
```

### Data Flow Examples

**Simple conditional with value transformation:**
```comp
{score=85} -> -?? score > 90 -&& "A" -|| "B"  // Outputs: "B"
```
The input struct flows in, the condition checks `score > 90` (false), so the else branch executes, outputting "B" to the pipeline.

**Chained conditions with different outputs:**
```comp
{age=25} ->
    -?? age < 18 -&& :restrict_access    // Returns restricted view
    -|? age < 21 -&& :limit_features     // Returns limited view  
    -|| :full_access                     // Returns full view
-> :render_page
```
The age=25 input means both conditions fail, so `:full_access` executes. Whatever `:full_access` returns becomes the input to `:render_page`.

**Multiple independent valve groups:**
```comp
data 
-> :validate -?? is_valid -&& :log_success -|| :log_error  // First group
-> :transform -?? needs_cache -&& :add_cache_headers       // Second group
-> :send_response
```
Each valve group is independent. The first group's output (from either `:log_success` or `:log_error`) becomes the input to the second valve group. The second group tests this new input with its own condition.

### Important Behaviors

**Pass-through on no match**: If no conditions match and no `-||` is provided, the original input passes through unchanged:
```comp
{value=10} -> -?? value > 100 -&& :process  // No match, no else
-> :next_step  // Receives {value=10} unchanged
```

**Early termination**: Once a condition matches, the valve group immediately executes that action and exits. Subsequent conditions are not evaluated:
```comp
{status="pending"} ->
    -?? status == "pending" -&& :queue_job     // This matches and executes
    -|? status == "pending" -&& :different     // Never evaluated
    -|| :default                               // Never evaluated
```

**Condition access to input**: All conditions in a valve group can reference the input value:
```comp
user ->
    -?? user.age >= 18 and user.verified -&& :full_access
    -|? user.parent_consent -&& :limited_access
    -|| :deny
```

### Key Benefits

1. **No ambiguity**: Each valve group is self-contained with clear boundaries
2. **No terminators needed**: The operators themselves define the structure  
3. **Consistent visual language**: Double-character operators form a clear family
4. **Readable flow**: `-??` asks a question, `-&&` provides the answer, `-|?` asks another, `-||` catches the rest
5. **Pipeline friendly**: Multiple valve groups can exist in sequence without interference
6. **Predictable data flow**: Input flows in, one action executes, output flows out

### Design Rationale

- The double characters make valve operations visually distinct from single-character pipeline operators (`->`, `..>`)
- The `-&&` separator is essential for parsing clarity between condition and action
- No blocks or special terminators required - the operators handle all cases
- Natural reading: "if?? this and&& do that, or-if? this and&& do that, or-else|| do this"
- Each valve group acts as a single transformation step in the pipeline, maintaining the language's functional flow philosophy
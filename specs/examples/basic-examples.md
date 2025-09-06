# Basic Comp Examples

These examples should all work when the implementation is complete. They serve as both documentation and test cases.

## Phase 1: Basic Operations

### Struct Operations

```comp
// Empty struct
{}

// Named fields
{x=10 y=20}

// Unnamed fields
{1 2 3}

// Mixed fields
{name="Alice" 30 active=#true}

// Spread operator
base = {x=1 y=2}
extended = {...base z=3}
// Result: {x=1 y=2 z=3}

// Override with spread
{x=1 y=2} -> {...@ x=10}
// Result: {x=10 y=2}
```

### Pipeline Operations

```comp
// Basic pipeline
5 -> double
// Result: 10

// Struct transformation
{x=1 y=2} -> {sum=x+y}
// Result: {sum=3}

// Chained pipelines
{5} -> double -> {result=@}
// Result: {result=10}
```

## Phase 2: Functions and Control Flow

### Function Definitions

```comp
// Simple function
!func :double = {
    @ * 2
}

// Function with pattern matching
!func :describe = @ -> match {
    0 -> "zero"
    1 -> "one"
    n -> "many"
}

// Function using struct fields
!func :add_point = {
    {x=@.x1 + @.x2, y=@.y1 + @.y2}
}
```

### Iteration

```comp
// Map over collection
{1 2 3} => @ * 2
// Result: {2 4 6}

// With index
{10 20 30} => {value=@ index=@idx}
// Result: {{value=10 index=0} {value=20 index=1} {value=30 index=2}}

// Filter and map
{1 2 3 4 5} => @ % 2 == 0 ? @ * 10 : @skip
// Result: {20 40}
```

## Phase 3: Shapes and Types

### Shape Definitions

```comp
!shape ~Point = {
    x ~number
    y ~number
}

!shape ~Circle = {
    center ~Point
    radius ~number(>0)
}

!shape ~Rectangle = {
    topLeft ~Point
    width ~number(>0)
    height ~number(>0)
}
```

### Shape Usage

```comp
// Apply shape
raw_data = {x=10 y=20}
point = raw_data ~ Point

// Check shape
is_valid = data ~? Point

// Shape with defaults
!shape ~Config = {
    host ~string = "localhost"
    port ~number(1..65535) = 8080
    debug ~bool = #false
}

partial = {port=3000}
config = partial ~ Config
// Result: {host="localhost" port=3000 debug=#false}
```

## Phase 4: Real-World Examples

### List Comprehension (Python equivalent)

```comp
// Python: [fruit.upper() for fruit in fruits]
fruits = {"Banana" "Apple" "Lime"}
loud_fruits = fruits => :string:upper
// Result: {"BANANA" "APPLE" "LIME"}

// Python: [(i, fruit) for i, fruit in enumerate(fruits)]
enumerated = fruits => {index=@idx fruit=@}
// Result: {{index=0 fruit="Banana"} {index=1 fruit="Apple"} {index=2 fruit="Lime"}}
```

### Shopping Cart

```comp
!shape ~Item = {
    name ~string
    price ~number(>0)
    quantity ~number(>=0)
}

!shape ~Cart = {
    items ~Item[]
    discount ~number(0..1) = 0
}

!func :add_item ~{cart ~Cart item ~Item} = {
    // Find existing item or add new
    $existing = cart.items => name == item.name ?> @ : @skip -> :first
    $updated = $existing ? 
        {...$existing quantity=quantity + item.quantity} : 
        item
    
    $items = cart.items => name == item.name ? $updated : @
    {...cart items=$items}
}

!func :calculate_total ~Cart = {
    items => (price * quantity) -> :sum -> @ * (1 - discount)
}

// Usage
cart = {} ~ Cart
cart = {cart=cart item={name="Apple" price=1.00 quantity=3}} -> :add_item
cart = {cart=cart item={name="Banana" price=0.50 quantity=6}} -> :add_item
total = cart -> :calculate_total
```

### Data Processing Pipeline

```comp
// Process CSV-like data
data = {
    {name="Alice" age=30 dept="Engineering"}
    {name="Bob" age=25 dept="Marketing"}
    {name="Charlie" age=35 dept="Engineering"}
}

// Find average age by department
by_dept = data => {dept=dept ages={age}} 
    -> :group_by:dept 
    => {dept=dept avg_age=ages->:average}

// Result: {
//   {dept="Engineering" avg_age=32.5}
//   {dept="Marketing" avg_age=25}
// }
```

## Testing Strategy

Each example should have:
1. **Parser test**: Can it be parsed?
2. **AST test**: Is the AST structure correct?
3. **Evaluation test**: Does it produce the right result?
4. **Error test**: Does it fail appropriately on bad input?

Example test structure:
```python
def test_struct_spread():
    code = "{x=1 y=2} -> {...@ z=3}"
    ast = parse(code)
    assert isinstance(ast, Pipeline)
    
    result = evaluate(ast)
    assert result == {"x": 1, "y": 2, "z": 3}
```
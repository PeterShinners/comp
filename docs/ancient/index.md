# Python-ish++ Language

A language that works in the python runtime, but it slightly different

- Self is not an argument
- Do not use import, some other keyword
- Also explicit export
- Anonymous code blocks to replace “map() style methods with lambda”
- Rust-like enums
- Rust-like structures with `impl`  instead of classes and subclasses
    - Use decorators instead of rust’s `!implement[’xyz’]` garbage
    - No `__init__`  ; functions always generate or copy new classes
- Pytest like definition of contexts and data that can be referenced downstream but not as explicit arguments. (some global `context`  type object that is shared down callstack)
    - no auto-outer scope or lambda
- Rust-style question marks in method names (makes python interop too hard?)
- Rust-style const by default, `mut` is a keyword

```python
struct X:
	name
	age

impl cls for X:
	def init(args):
		ctx.log.debug("created a X")
		return X{name="unknown", age=0}

	def compute(a, b, c):
    a.map() as ii:
			yield ii * 2
	  .filter() as ff:
	    yield not ff // 8
		.sum()
		ret
```

so no for? no if else? (use match instead?)

```python
asdf
ctx.Type.value = 123  # pops when leaving current context?
myfunc1()

def myfunc1():
	print(ctx.Type.value)
	ctx[Type].whatever   # or this? could ctx be a module too, any object?

```

every block generates a value, this is how iterators can work without yield?

Return is like rusts async that uses async as a postfix operator. “expression expression expression <return. If a block must be a value, are multiple return statements a thing? I want this, perhaps this becomes nested blocks? sounds messy….

An awesome language should be the preferred format of choice for ui markups. Not json or qml or whatever. How well can a language lend itself to modeling data without boilerplate

Composability! (random keyword that makes me happy)

Can something like linq work when chaining/composing operators. Something that can analyze the chain of operators and combine them into more efficient queries? `paths as p: filter(p.size() > 1000mb`

Rust uses postfix .await. Could this lang use postfix .return. The await as postfix has a benefit that the results can be chained. Return doesn’t allow that, it always terminates a statement. The `?` in rust is also postfix

```python
# how to postfix return and have multiple exits from a block
{
	condition.isvalid():
		"primary"<<
	.else():
		"secondary"<<
}
```

This example has a couple confusing points. Each condition block wants to exit out of the parent block, not just itself. Also, the condition generates a value of some “resolved_if” type, which allows chaining the .else() method. It that a valid thing, or getting too abstracty? 

So a number of postfix arrows controls how many blocks the return comes from?

If there was no way to double-return, the code would look like

```python
{
	condition.isvalid():
		"primary"<
	.else():
		"secondary"<
	<
```

Preferring rust’s “final statement is returned” logic

What about prefix `=` as the return statement (seemsgood)

A method that takes a block is something else. They generate a value like normal, but can also be “chained”, which the compiler dispatches and connects. But the result is always a regular value

Also, isinstance is replaced with an operator. `is` or `is a`? Normal use of python’s is is gone.

```python
val.istype(Number):
	=val + 1
.istype(Point):
	=Point{val.x + 1, val.y + 1}
```

What if there are no operators. Everything is accesssed through some type (or module) as a function.

```python
def math.abs(val):
	=with val .istype(Number):
		=val.math.add(1)
	.istype(Point):
		=val.x**2 + val.y**2
```

But operators like `+` could be sugar for `.ops.add` . Not liking the prefix `=` everywhere.

Do not need to prefix methods with a type. A type defines an ordered list of implementations it can use, and handles method resolution. Instead of inserting or appending types code can modify the list of implementations? If so, that is done inside the current context, nobody else gets that.

```python
using numpy  # defines a point and some impls
using gamemath  # also defines impls for a point 

def distance(value):
	if(val.is(Number)):
		val.abs()
	else(val.is(Point)):
		val.x ** 2 + val.y ** 2
```

This `if` and `else` are recognized as special things because they open a block. would be nice if they can pass values into the block (or define something in the shared context).

Could be awesome if arguments were passed lazily to functions. An arg that is never used never gets computed? Plus an arg can then be introspected as a possible “block of code to execute” and could be evaluated multiple times. Perhaps that is what these “blocks” are, and do not apply to regular arguments.

blocks are like named arguments to some method that only gets a single value, the block..

```python
if(condition):
	block_1
elif(condition2):
  block_2
else():
	block_3

try():
	block_1
finally():
	block_2

for(iterator) as loop:
  block_1
	loop.continue()
	loop.break()
else():
	no_break
```

Python ‘elif’ condition is never evaluated if the first condition is true. It’s like the argument to if() and elif() are like a block themselves…

So a function that takes a block can have its parenthesis omitted? `if` becomes a function that takes two blocks. could be written `if (condition, action)` or `if condition: action` ? Is a colon an argument separate for block arguments outside parenthesis? 

Could keywords like “break” be defined inside the block they run in? Same as “return” inside a def block? Seems fantastic. So keywords are some identifer that the block owner can define. Whenever the token appears it is somehow evaluated?

```python
def whilefunc(block condition, block operation):
    result = condition.evaluate()
    if not result:
			return
		keywords = {continue=ContinueOperator(), break=BreakOperator(), result=result}
		exitop = operation.evaluate(keyworks=keywords)
		
		if exitop not in (ReturnOperator, keywords["continue"]):
			return exitop.value
		whilefunc(condition, operation)
		
whilefunc condition:
	operation
	continue
```

This potentially makes ide’s very complicated? The block should be a predefined structure that can be well documented and analyzed. Not a runtime defined collection of data. (at least, for traditional cases)

What if curly brackets defined a “lazy” evaluation. Sort of like a generator. Sort of fits the C++ style of block definitions

```python
while {conditional} {operation}

if CONSTANT {operation}
elif {condition2} {op2}
else {op3}
```

And then, like candy-lang, a curly brackets block can optionally be defined by an indented section

```python
while {condition}:
	operation

if CONSTANT:
	opertaion
elif {condition}:
	op2
else:
	op3
```

Applying a block to an object is done without parenthesis. It’s something different than a `__call__` . It is like `__block__(name, code)` . But again, don’t want arbitrary naming because the language is too hard to define. So the structure of blocks must be some analytical object. 

Overnight, literal, mind-blowing ideas

- There are no method calls, a name with parenthesis and args is a type and constructor. Only immutable types are created. And something about types can have blocks sent to them.
- Avoid using int/str types directly, always wrapped in an object Year(1990), Path(’/root’)
- The values in an object can be called as if they were that object, as long as there is only one ; data values define mro. Type{fileobj a, user b}; t=Type(…); t {read(1024)}
- Some way that a block/method thing can be applied to an iterator of values. Works like Tessa’s groups naturally. Invokcations keep track of the incoming iterators and provide named references. The iterator naturally keeps its current values, perhaps has a builtin “back” and “twoback” :-) and can reference any previous step that has a label applied.
- Errors then handled more like rust, Option() and Result() objects. Still prefer something better than panic!
    - But this means ? operator could only work when created result types, seems lessgood.
    - I more like the ‘block of code exist reason’ recently touched. But if most things are going to be type constructors then blocks won’t be common?
- Instead of modifyable lists, focus on assembling iterators. Remember we want to steer towards map(), filter(), etc. Not so much random access. A collection of iterator instructions can be dropped into an immutable container :-)
- I suppose similar for arbitrary dictionary types? Iterating key/values might be preferred, but at some point people will want an arbitrary collection of data.

Perhaps swap the function call and block ideas. Since building an instance doesn’t afford much logic, it is just assigning values to attributes

```python
Define Distance{float}
Define(Point):
	x:Distance
	y:Distance
	z:Distance=0.0

impl Point.normalize:
  distance = Distance{x*x + y*y + z*z};
  if(distance==0.0):
		Fail("Zero length distance")
  return Point{x/distance, y/distance, z/distance}

a = Point(1,2,3)
b = a.normalize()
```

In the `distance==0` since equal is not defined for Distance it is defined by the first member that does define it (in this case, float?)
return is a function/keyword injected by the impl block

These block definitions are primarily defined by static analyzable statements

DefineBlock impl(args):
ExitKeyword return(value)
ValueKeyword self = something?
ValueKeyword cls = something?

DefineBlock if(condition):
Followup elif, else

DefineBlock while(condition):
ExitKeyword break
ExitKeyword continue

Since a block defines what keywords it will provide, we can at compile time
error if code in the block uses an undefined keyword. This rocks!

As python implementation, consider using msgspec as the data backend for these immutable objects
Need a syntax to modify a value in a block

obj.attr = value  # This could be made to work, it implies a copy of obj? Actually must be
obj = obj.attr = value

instead aim for rust's copy, but better.

obj = obj{name=value, ..obj}  # Note we're using a value to construct a new object (using its type)

If brackets are sugar for indented blocks does that mean this is the same?

obj = obj:
name=value
..obj

Does this mean if/while blocks are simple objects constructing a value? It feels like
*NO* because constructing a value is invoked immediately, where blocks are passed
to the owner to be dealt with.

This feels like it's leaning back to the 'morning idea' that object construction uses
parenthesis and block definition uses curly/block syntax

BUT - code still wants `while (condition) {block}` . This leans back towards parens
evaluate immediately but curlies define a block object.  This is feeling like
`while` keyword is not a regular function call, but a structure that requires two
block objects?

while {condition}:
block

how does this jive with methods like map and filter?

lines.filter:
line.contains("=")
map:
line.split("=",1)[0]

How could this be possible. It can't be. Perhaps if `map` becomes `.map` to
define a contiuation of the code. This could also be

lines.filter{line.contains("=")} .map{line.split("=", 1)[0]}

But where is "line" coming from. Not interested in doing `|line|` like Rust.
Maybe more like `as line` like python contexts.

lines.filter as line:
line.contains("=")

Or perhaps the filter can look more like a function call, taking a token of the
name to inject into the block?

lines.filter(l):
l.contains("=")

But now this implies a "dynamic" namespace inside the block. Was hoping early that
a block namespace is statically known. (which it could be if the name is required
to be part of the call syntax?)

Or the `filter` predefines the name of the value inside its loop. That could get odd
if there is a filter inside of a filter? (filtering characters inside filtering lines of text?)
That way the block could get access to other cool things, like 'progress'?

lines.filter:
print(filter.progress)
filter.value.contains("=")

But unlike an if{} block, these blocks have a job to produce a value. This goes
back to the idea of "What if filter was a type"

Iter lines
.filter:
log('value')
filter.value.contains('=')

so filter is a type that accepts needs a boolan value?

DefineBlock filter:
singleiter: bool

That makes

.filter:
log('value') ,
filter.value.contains('=')

the construction of an object with two values. Which is compile error because
filter is known to be a single value.

====

what about there being no "equals" operator? that seems dumb, code needs
name = obj{} to store a constructed value. Perhaps no attribute assignment
then. `name.attr = obj{}` can never be done. no mutability

# monthslater

No operators, no attributes, no global functions, only methods, loops and conditionals are methods

different brackets only have single use. generating object {}, call method (), what about square[]?

is this possible? consistency so good? 

a function is a type? don’t like that calling a type creates it in python. but this might not be quite right. instead lean on creating a structure with a type name `mytype {...data}`. But then what if I want to call a method `buildatype(args)` . want these to be the same. making the first look like a function call is what leads to ‘functions are types’

```python
data { Point {x,y} }
func origin { Point {0,0} }
func distance (a,b) { a.x.mult(a.y).square(2).plus(b.x.mult(b.y).square(2)).square(0.5) }
len = distance( Point{2,2}, origin() }
```

or,

every function call gets args (optional if no args) and an optional block of code. an “else” can work because the “if” returns some sort of context object, so else becomes `.else`?

for loop needs a way to define a variable only for inside the context. perhaps that is why there is a ‘context’ type of global that allows access to args, inner loop, “self”, and more. These aren’t accessed through global keywords. this also allows assigning into so children contexts can inherit state.

`ctx.args` access args to immediate function, `ctx.for` for for loop iterator. this leads to potential namespacing problem. what if i want `ctx.floatprecision=3` Maybe I can assign to a specific type. Then subclasses could also access. `ctx[float.precision] = 4` , `digits = self[cls.precision, 3]` . This seems good, so the first two examples become something like `ctx[func.arcs]` and `ctx[for.iter]`. seems a clumsy syntax to require for any looping construct.

Can methods export values back to the ctx? primarily interested for things like ‘warnings’ or ‘errors’ coming out of a call. Perhaps there are mutable containers in the ctx. 

what if there were no ‘function args’ or ‘function return value’, the ctx just has its own stack, `ctx[func.args] = {1,2,3}`, `sum()` , `total = ctx[sum.result]`

also, 

maybe every function is actually a generator. any function can produce a series of values. the language has syntax sugar for just getting the first item generated, or collecting all items. (could be cool if there was a modifier that could also provide the count)

Considering the concept of a single constructor type. Sort of like rusts `{}` to build any object type. Want the actual type to precede the object. Need an alternate for sequences? But also want named arguments for structs. `Point{x=1, y=2}` . Use the pairs here, so `Point{x:1, y:2}` also allows some amount of positionals? `Point{1, 2, velocity:up}`

perhaps `value:value` is a shorthand for building a pair. Then `a:b:c` builds a tuple like `((a,b),c)`. This allows a dictionary-like constructor to still accept a sequence of values. `dict{k1:v1, k2:v2}` .

Cool if there was a shorthand for “tokens”, which are string types, but defined by a valid token without needing all the quotes? 

Or if there are no variables and everything must be accessed through an object a token is easy to leave unquoted.  `token, local.var`, "literal.string". This means the pair for dictionaries with literals is easy, but value lookups aren’t complex either, `dict{key:value, args.a:args.b}`

CUE (configuration/data language)

looks amazing as a syntax for describing data structures. can we just add on a syntax for evaluation? I assume there is a python cue interpreter? still reading spec with two questions.. defining custom types (date, datetime, seems easily possible). 

CLUE, A new language where a function takes immutable struct in and passed a struct out. struct is also an array with digit based keys. struct is also a scalar if it only has one value, therefore a literal like 12 is a struct with a single integer, and can be used as such. Struct is also a lazy iterator that computes values as needed.

Block is a bracketed structure that defines code to create a structure. There may need to be some difference between a constructor that can be compiled and build time (constexpr) and a function.

Automatically converts between structs with compatible fields. Any block defines an anonymous type. calls chain from left to right. Use rust-like ..default syntax to copy fields from another object.

method calls have sigil modifiers that allow, iterating values, getting all values at once, getting number of values, checking if there are any values. some methods may provide specialized implementations for these sigils (although they all get a default implementation if normal iterate is defined)

for loop, while, and if all work as regular methods that accept a block argument.

There may also need to be a type definition that works like cue?

```python
define point {x number ?= 0.0, y number ?= 0.0}
define line (a: Point, b: point)

function distance {Line} {((arg.b.x-arg.a.x**2) + (arg.b.y-arg.a-y**2)) // 2)

origin = {} Point
up = {y=1} Point

dist = {origin, up} Line distance
```

maybe ‘define’ is a cue like definition, but can have no code. function is a block that is its own code.

local variables given underscores, else all variables are part of returned structure

Error handling done through a stack-shared context. Functions can install error handlers and it works like middleware. (this implies some new type of function that has pre, run original, and post phases.

Constructor can call functions, but cannot pass itself as a structure to other functions. this may encourage nesting structure, or some unexplored builder pattern?

The system provides a few builtin “infinite generators”. perhaps only one is really needed, an integer counter. everything can build from that.

[playground1](playground1.md)

[playground2](playground2.md)

[codexamples](codexamples.md)

going back to cue docs.

cool

- constraints (<5 for ints, etc)
    - give iterators a way to define a min or max of length (constraints)
- types are values
- order independent definitions
- optional fields followed by questionmark ?=
    - but I want makefile like conditional setting also?
        - 

unsure

- structs defined multiple times and are incrementally combined
- templates and conditions can almost define logic to fill out fields, but it is obtuse and perhaps more complicated than a small amount of code logic.

[nim examples](nim-examples.md)

have iterators and containers be two separate types, no longer trying to make them the same thing. A scalar value is an iterator of one. Still need some sort of ‘stream’ iterator that is lossy.

but, there’s still something nice about them being the same.

don’t allow assignment to fields or indexes, instead a new struct is always created, only copying the values it wants to change. some sort of `data={name=val,..data}` syntax? language uses lifetimes to possibly recycle structs that are never referenced again

still really like the idea where struct defined as block of code. just need a cool way to push values into the resulting struct. and there’s no way in that block to refer to the struct being built?

maybe locals are assigned similar to a python walrus op, not part of the outgoing struct

```python
define user {
   first= str
   last= str
   full= first + last str
}   
user { # defined by fields
    first= "peter" title
    last= "shinners" title
}
user { "peter" "shinners"}
```

but put the type last, like a method call

```python
{"peter" "shinners"} user
define title {
  str
  letters:= $arg str characters
  letters uppercase  # iterate first character and call upper
  ..letters  # iterate all remaining chars
}
```

[Struct in Struct out](struct-in-struct-out.md)

[threejs example](threejs-example.md)

[fastapi examples](fastapi-examples.md)

[structs and calls](structs-and-calls.md)

Name?

**Petal** or **Pettle**, file extension `.pet`? (or possibly `.ptl` if taken)

[Subclassy stuff](subclassey-stuff.md)

[https://rhombus-lang.org/](https://rhombus-lang.org/)

Rhombus has a few cool looking things. I like the ‘patterny list comprehensions`[a + 1, …]`

Goals

- All funcs take a single arg in and a single arg out
- There are is now flow control, blocks are a first class thing
    - A block and an object definition is the same thing
    - The way functions do map() or for() loops are identical
- Objects are read only, easy ways to overlay a set of wrapped changes around an object
- There are inherited objects for runtime, scope, thread, process, etc
    - These are inherited down into any call
    - (Allows a style like envvars/cmdline args for all language functions
- Object definitions define the shape of an object. A stack+object is compatible with any call that the call requires
- The language is designed around chaining calls from left to right
    - Some sort of walrus assignment during chains
    - optional early out on failures, or fallback values
- Language compiler challenge. Allow static analysis to work. Although on data read from outside code (ie, json) there needs to be a one-time validation into a known defined object type.
- Handy operators for extracting sets of values between objects/dicts
- Objects have the ability to be evaluated lazily? An object is also an iterator… there’s some sort of “next value” key that can be assigned to
    - This assignment is the return value, no need for return statements
    - Maybe this is what some ‘away’ type syntax is for, to have computed function run on demand
- Way to wrap class implementations like middleware; run code before, run code after, but no need to redefine documentation, args, and lameness. Perhaps can extend definition (this one extra arg, append to docstring…)
- Perhaps values are always referenced from some dotted container and attribute name.
    - There are no globals or bare variables.
- Common context assignment may be a “as default” or ?= so overrides can push from outer contexts?
- Modules aren’t generally imported except at the starting/toplevel. They are placed into an outer context (perhaps not even by code, but some project definition?)
    - There is a “standard library context” tools can opt into (or override, or replace, or ignore?)

[Examples v7](examples-v7.md)